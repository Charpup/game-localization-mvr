#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
async_adapter.py - Async/Concurrent Execution for Game Localization Pipeline

This module provides async versions of core functions for lower latency processing:
- AsyncLLMClient: Asynchronous LLM client with semaphore-based concurrency control
- AsyncPipeline: Streaming pipeline for parallel stage execution
- process_csv_async: Main entry point for async CSV processing

Target: 30-50% latency reduction on large datasets through:
- Concurrent LLM calls with rate limiting
- Pipeline parallelization (normalize → translate → QA → export overlap)
- Stream processing with buffer management
- Async file I/O

Author: Async Implementation Task P3.4
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Coroutine,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
)

import aiofiles
import aiohttp
import yaml

# Import from existing runtime_adapter for compatibility
from scripts.runtime_adapter import (
    LLMResult,
    LLMError,
    LLMRouter,
    BatchConfig,
    get_batch_config,
    _estimate_tokens,
    _estimate_cost,
    _extract_usage,
    _trace,
    _safe_int,
    CHARS_PER_TOKEN,
)

# ============================================================================
# Configuration
# ============================================================================

DEFAULT_ASYNC_CONFIG = {
    "enabled": True,
    "max_concurrent_llm_calls": 10,
    "semaphore_timeout": 60,
    "buffer_size": 100,
    "max_workers": 4,
    "pipeline_stages": ["normalize", "translate", "qa", "export"],
    "stage_concurrency": {
        "normalize": 5,
        "translate": 10,
        "qa": 8,
        "export": 3,
    },
    "enable_streaming": True,
    "backpressure_enabled": True,
    "queue_maxsize": 200,
}


def load_async_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load async configuration from pipeline.yaml or use defaults."""
    if config_path is None:
        # Try to find config relative to script location
        script_dir = Path(__file__).parent.parent
        config_path = script_dir / "config" / "pipeline.yaml"
    
    config = DEFAULT_ASYNC_CONFIG.copy()
    
    if Path(config_path).exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f) or {}
                if 'async' in yaml_config:
                    config.update(yaml_config['async'])
        except Exception as e:
            _trace({
                "type": "async_config_load_error",
                "error": str(e),
                "config_path": str(config_path)
            })
    
    return config


# ============================================================================
# Async LLM Client
# ============================================================================

@dataclass
class AsyncLLMResult:
    """Result of an async LLM call."""
    text: str
    latency_ms: int
    raw: Optional[dict] = None
    request_id: Optional[str] = None
    usage: Optional[dict] = None
    model: Optional[str] = None
    
    def to_sync_result(self) -> LLMResult:
        """Convert to sync LLMResult for compatibility."""
        return LLMResult(
            text=self.text,
            latency_ms=self.latency_ms,
            raw=self.raw,
            request_id=self.request_id,
            usage=self.usage,
            model=self.model
        )


class AsyncLLMClient:
    """
    Asynchronous LLM client with concurrency control.
    
    Features:
    - Semaphore-based concurrent call limiting
    - Per-model concurrency configuration
    - Backpressure handling
    - Connection pooling via aiohttp
    - Compatible with existing LLMRouter
    
    Usage:
        client = AsyncLLMClient(max_concurrent=10)
        result = await client.chat(
            system="You are helpful.",
            user="Hello!",
            metadata={"step": "translate"}
        )
    """
    
    # Shared router and semaphore instances
    _router: Optional[LLMRouter] = None
    _semaphore: Optional[asyncio.Semaphore] = None
    _model_semaphores: Dict[str, asyncio.Semaphore] = {}
    _session: Optional[aiohttp.ClientSession] = None
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_s: Optional[int] = None,
        max_concurrent: Optional[int] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize async LLM client.
        
        Args:
            base_url: API base URL (defaults to LLM_BASE_URL env)
            api_key: API key (defaults to LLM_API_KEY env)
            model: Default model (defaults to LLM_MODEL env)
            timeout_s: Request timeout in seconds
            max_concurrent: Global max concurrent calls
            config: Async configuration dict
        """
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "")).strip().rstrip("/")
        self.api_key = (api_key or self._load_api_key()).strip()
        self.default_model = (model or os.getenv("LLM_MODEL", "")).strip()
        self.timeout_s = timeout_s or int(os.getenv("LLM_TIMEOUT_S", "60"))
        
        # Load or use provided config
        self.config = config or load_async_config()
        self.max_concurrent = max_concurrent or self.config.get("max_concurrent_llm_calls", 10)
        self.semaphore_timeout = self.config.get("semaphore_timeout", 60)
        
        # Initialize router
        if AsyncLLMClient._router is None:
            AsyncLLMClient._router = LLMRouter()
        self.router = AsyncLLMClient._router
        
        # Initialize semaphores lazily
        self._initialized = False
    
    def _load_api_key(self) -> str:
        """Load API key with file-based injection support."""
        key_file = os.getenv("LLM_API_KEY_FILE", "").strip()
        if key_file and os.path.exists(key_file):
            try:
                with open(key_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                for line in content.splitlines():
                    line = line.strip()
                    if line.lower().startswith("api key:"):
                        return line.split(":", 1)[1].strip()
                    elif line.lower().startswith("api_key:"):
                        return line.split(":", 1)[1].strip()
                if content and '\n' not in content and ':' not in content:
                    return content
            except Exception:
                pass
        return os.getenv("LLM_API_KEY", "")
    
    async def _initialize(self):
        """Lazy initialization of semaphores and session."""
        if self._initialized:
            return
        
        # Global semaphore for all LLM calls
        if AsyncLLMClient._semaphore is None:
            AsyncLLMClient._semaphore = asyncio.Semaphore(self.max_concurrent)
        
        # Per-model semaphores for fine-grained control
        stage_concurrency = self.config.get("stage_concurrency", {})
        for stage, limit in stage_concurrency.items():
            if stage not in AsyncLLMClient._model_semaphores:
                AsyncLLMClient._model_semaphores[stage] = asyncio.Semaphore(limit)
        
        # aiohttp session with connection pooling
        if AsyncLLMClient._session is None or AsyncLLMClient._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout_s, connect=10)
            conn = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=20,
                enable_cleanup_closed=True,
                force_close=False,
            )
            AsyncLLMClient._session = aiohttp.ClientSession(
                connector=conn,
                timeout=timeout,
                headers={"Content-Type": "application/json"}
            )
        
        self._initialized = True
    
    async def close(self):
        """Close the client session."""
        if AsyncLLMClient._session and not AsyncLLMClient._session.closed:
            await AsyncLLMClient._session.close()
            AsyncLLMClient._session = None
    
    async def __aenter__(self):
        await self._initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def chat(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        semaphore: Optional[asyncio.Semaphore] = None,
    ) -> AsyncLLMResult:
        """
        Send an async chat completion request.
        
        Args:
            system: System prompt
            user: User message
            temperature: Sampling temperature
            max_tokens: Max tokens limit
            response_format: Response format dict
            metadata: Metadata for routing and tracing
            timeout: Request timeout override
            semaphore: Optional custom semaphore for this call
            
        Returns:
            AsyncLLMResult with response data
        """
        await self._initialize()
        
        # Validate config
        if not self.base_url or not self.api_key:
            raise LLMError(
                "config",
                "Missing LLM configuration. Set env vars: LLM_BASE_URL, LLM_API_KEY",
                retryable=False
            )
        
        # Extract routing context
        step = "_default"
        model_override = None
        if isinstance(metadata, dict):
            step = metadata.get("step", "_default")
            model_override = metadata.get("model_override")
        
        # Get config params
        config_params = self.router.get_generation_params(step) if self.router.enabled else {}
        final_temp = temperature if temperature is not None else config_params.get("temperature", 0.2)
        final_max_tokens = max_tokens if max_tokens is not None else config_params.get("max_tokens")
        final_resp_format = response_format if response_format is not None else config_params.get("response_format")
        
        # Build model chain
        if model_override:
            model_chain = [model_override]
        elif self.router.enabled:
            model_chain = self.router.get_model_chain(step)
        else:
            model_chain = []
        
        if not model_chain and self.default_model:
            model_chain = [self.default_model]
        
        if not model_chain:
            raise LLMError(
                "config",
                f"No model configured for step '{step}'",
                retryable=False
            )
        
        # Try each model in chain with fallback
        last_error: Optional[LLMError] = None
        for attempt_no, model in enumerate(model_chain):
            try:
                result = await self._call_single_model(
                    model=model,
                    system=system,
                    user=user,
                    temperature=final_temp,
                    max_tokens=final_max_tokens,
                    response_format=final_resp_format,
                    metadata=metadata,
                    step=step,
                    attempt_no=attempt_no,
                    timeout=timeout,
                    semaphore=semaphore,
                )
                return result
            except LLMError as e:
                last_error = e
                if attempt_no < len(model_chain) - 1 and self.router.should_fallback(e):
                    continue
                raise
        
        if last_error:
            raise last_error
        raise LLMError("config", "No models available", retryable=False)
    
    async def _call_single_model(
        self,
        model: str,
        system: str,
        user: str,
        temperature: float,
        max_tokens: Optional[int],
        response_format: Optional[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]],
        step: str,
        attempt_no: int,
        timeout: Optional[int] = None,
        semaphore: Optional[asyncio.Semaphore] = None,
    ) -> AsyncLLMResult:
        """Execute a single async model call with semaphore control."""
        
        # Determine which semaphore to use
        sem = semaphore or AsyncLLMClient._semaphore
        stage_sem = AsyncLLMClient._model_semaphores.get(step)
        
        # Build payload
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload: Dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if response_format:
            payload["response_format"] = response_format
        
        # Use semaphore with timeout for backpressure
        t0 = time.time()
        
        try:
            # Wait for semaphore with timeout
            if sem:
                await asyncio.wait_for(
                    sem.acquire(),
                    timeout=self.semaphore_timeout
                )
            
            # Also acquire stage-specific semaphore if exists
            if stage_sem and stage_sem != sem:
                await asyncio.wait_for(
                    stage_sem.acquire(),
                    timeout=self.semaphore_timeout
                )
            
            try:
                effective_timeout = timeout or self.timeout_s
                
                async with AsyncLLMClient._session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=effective_timeout
                ) as resp:
                    latency_ms = int((time.time() - t0) * 1000)
                    
                    # Handle HTTP errors
                    if resp.status in (429, 500, 502, 503, 504):
                        text = await resp.text()
                        raise LLMError(
                            "upstream",
                            f"Upstream error HTTP {resp.status}: {text[:200]}",
                            retryable=True,
                            http_status=resp.status
                        )
                    
                    if resp.status >= 400:
                        text = await resp.text()
                        raise LLMError(
                            "http",
                            f"HTTP error {resp.status}: {text[:200]}",
                            retryable=False,
                            http_status=resp.status
                        )
                    
                    # Parse response
                    try:
                        data = await resp.json()
                        text_content = data["choices"][0]["message"]["content"]
                    except Exception as e:
                        raise LLMError(
                            "parse",
                            f"Response parse error: {e}",
                            retryable=True
                        )
                    
                    # Extract metadata
                    request_id = data.get("id")
                    usage = _extract_usage(data)
                    usage_present = bool(usage)
                    
                    # Token estimation
                    req_chars = len(system) + len(user)
                    resp_chars = len(text_content or "")
                    
                    if usage and usage.get("prompt_tokens"):
                        prompt_tokens = usage["prompt_tokens"]
                        completion_tokens = usage.get("completion_tokens", 0)
                        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
                        usage_source = "api_usage"
                    else:
                        prompt_tokens = _estimate_tokens(system) + _estimate_tokens(user)
                        completion_tokens = _estimate_tokens(text_content or "")
                        total_tokens = prompt_tokens + completion_tokens
                        usage_source = "local_estimate"
                    
                    cost_usd_est = _estimate_cost(model, prompt_tokens, completion_tokens)
                    
                    # Trace event
                    trace_event = {
                        "type": "llm_call_async",
                        "ts": datetime.now().isoformat(),
                        "step": step,
                        "request_id": request_id,
                        "latency_ms": latency_ms,
                        "req_chars": req_chars,
                        "resp_chars": resp_chars,
                        "base_url": self.base_url,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                        "usage_source": usage_source,
                        "usage_present": usage_present,
                        "cost_usd_est": cost_usd_est,
                        "selected_model": model,
                        "attempt_no": attempt_no,
                    }
                    
                    if isinstance(metadata, dict):
                        batch_idx = metadata.get("batch_idx")
                        if batch_idx is not None:
                            trace_event["batch_id"] = f"{step}:{batch_idx:06d}"
                    
                    _trace(trace_event)
                    
                    return AsyncLLMResult(
                        text=text_content,
                        latency_ms=latency_ms,
                        raw=data,
                        request_id=request_id,
                        usage=usage,
                        model=model
                    )
            
            finally:
                # Release semaphores
                if sem:
                    sem.release()
                if stage_sem and stage_sem != sem:
                    stage_sem.release()
        
        except asyncio.TimeoutError:
            raise LLMError(
                "timeout",
                f"Semaphore timeout after {self.semaphore_timeout}s",
                retryable=True
            )
    
    async def batch_chat(
        self,
        prompts: List[Dict[str, Any]],
        max_concurrent: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[AsyncLLMResult]:
        """
        Process multiple chat calls concurrently.
        
        Args:
            prompts: List of prompt dicts with 'system', 'user', 'metadata'
            max_concurrent: Override max concurrent calls for this batch
            progress_callback: Called with (completed, total) after each completion
            
        Returns:
            List of AsyncLLMResult in same order as prompts
        """
        await self._initialize()
        
        semaphore = None
        if max_concurrent:
            semaphore = asyncio.Semaphore(max_concurrent)
        
        completed = 0
        total = len(prompts)
        
        async def call_with_index(idx: int, prompt: Dict[str, Any]) -> tuple[int, AsyncLLMResult]:
            nonlocal completed
            result = await self.chat(
                system=prompt.get("system", ""),
                user=prompt.get("user", ""),
                temperature=prompt.get("temperature"),
                max_tokens=prompt.get("max_tokens"),
                response_format=prompt.get("response_format"),
                metadata=prompt.get("metadata"),
                timeout=prompt.get("timeout"),
                semaphore=semaphore,
            )
            completed += 1
            if progress_callback:
                progress_callback(completed, total)
            return idx, result
        
        # Create tasks for all prompts
        tasks = [call_with_index(i, p) for i, p in enumerate(prompts)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Sort by index and handle errors
        sorted_results = sorted(results, key=lambda x: x[0] if isinstance(x, tuple) else -1)
        output = []
        for item in sorted_results:
            if isinstance(item, tuple):
                output.append(item[1])
            else:
                # Error case
                output.append(AsyncLLMResult(
                    text="",
                    latency_ms=0,
                    raw=None,
                    request_id=None,
                    usage=None,
                    model=None
                ))
        
        return output


# ============================================================================
# Async File I/O
# ============================================================================

class AsyncFileIO:
    """Async file I/O operations for CSV reading/writing."""
    
    @staticmethod
    async def read_csv_async(
        file_path: str,
        encoding: str = 'utf-8'
    ) -> List[Dict[str, Any]]:
        """
        Read CSV file asynchronously.
        
        Args:
            file_path: Path to CSV file
            encoding: File encoding
            
        Returns:
            List of row dictionaries
        """
        rows = []
        async with aiofiles.open(file_path, 'r', encoding=encoding) as f:
            content = await f.read()
            # Use csv module in executor to avoid blocking
            loop = asyncio.get_event_loop()
            rows = await loop.run_in_executor(
                None,
                lambda: list(csv.DictReader(content.splitlines()))
            )
        return rows
    
    @staticmethod
    async def write_csv_async(
        file_path: str,
        rows: List[Dict[str, Any]],
        fieldnames: Optional[List[str]] = None,
        encoding: str = 'utf-8'
    ) -> None:
        """
        Write CSV file asynchronously.
        
        Args:
            file_path: Output file path
            rows: List of row dictionaries
            fieldnames: Column names (auto-detected if not provided)
            encoding: File encoding
        """
        if not rows:
            return
        
        if fieldnames is None:
            fieldnames = list(rows[0].keys())
        
        # Build CSV content in executor
        loop = asyncio.get_event_loop()
        
        def build_csv():
            import io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            return output.getvalue()
        
        content = await loop.run_in_executor(None, build_csv)
        
        async with aiofiles.open(file_path, 'w', encoding=encoding) as f:
            await f.write(content)
    
    @staticmethod
    async def read_jsonl_async(
        file_path: str,
        encoding: str = 'utf-8'
    ) -> List[Dict[str, Any]]:
        """Read JSONL file asynchronously."""
        rows = []
        async with aiofiles.open(file_path, 'r', encoding=encoding) as f:
            async for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return rows
    
    @staticmethod
    async def write_jsonl_async(
        file_path: str,
        rows: List[Dict[str, Any]],
        encoding: str = 'utf-8'
    ) -> None:
        """Write JSONL file asynchronously."""
        lines = [json.dumps(row, ensure_ascii=False) for row in rows]
        content = '\n'.join(lines) + '\n' if lines else ''
        async with aiofiles.open(file_path, 'w', encoding=encoding) as f:
            await f.write(content)


# ============================================================================
# Pipeline Components
# ============================================================================

T = TypeVar('T')


@dataclass
class PipelineItem(Generic[T]):
    """Item flowing through the pipeline."""
    data: T
    stage: str = "pending"
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


class PipelineStage(Generic[T]):
    """Base class for pipeline stages."""
    
    def __init__(self, name: str, concurrency: int = 5):
        self.name = name
        self.concurrency = concurrency
        self.input_queue: asyncio.Queue = asyncio.Queue()
        self.output_queue: asyncio.Queue = asyncio.Queue()
        self._workers: List[asyncio.Task] = []
        self._running = False
    
    async def start(self):
        """Start stage workers."""
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker_loop())
            for _ in range(self.concurrency)
        ]
    
    async def stop(self):
        """Stop stage workers."""
        self._running = False
        # Wait for all workers to finish
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
            self._workers = []
    
    async def _worker_loop(self):
        """Worker loop processing items from input queue."""
        while self._running:
            try:
                item: PipelineItem = await asyncio.wait_for(
                    self.input_queue.get(),
                    timeout=1.0
                )
            except asyncio.TimeoutError:
                continue
            
            try:
                result = await self.process(item.data)
                item.data = result
                item.stage = self.name
                await self.output_queue.put(item)
            except Exception as e:
                item.error = str(e)
                item.stage = f"{self.name}_error"
                await self.output_queue.put(item)
            finally:
                self.input_queue.task_done()
    
    async def process(self, data: T) -> T:
        """Process data - override in subclasses."""
        raise NotImplementedError
    
    async def put(self, item: PipelineItem) -> None:
        """Put item into input queue."""
        await self.input_queue.put(item)
    
    async def get(self) -> PipelineItem:
        """Get item from output queue."""
        return await self.output_queue.get()
    
    def get_output_queue(self) -> asyncio.Queue:
        """Get output queue for chaining."""
        return self.output_queue


class AsyncPipeline(Generic[T]):
    """
    Streaming pipeline for concurrent stage execution.
    
    Allows stages to overlap: translation can start before
    all normalization completes, etc.
    
    Usage:
        pipeline = AsyncPipeline()
        pipeline.add_stage("normalize", NormalizeStage())
        pipeline.add_stage("translate", TranslateStage())
        pipeline.add_stage("qa", QAStage())
        pipeline.add_stage("export", ExportStage())
        
        async for result in pipeline.process_stream(items):
            print(result)
    """
    
    def __init__(
        self,
        buffer_size: int = 100,
        backpressure_enabled: bool = True,
    ):
        self.stages: Dict[str, PipelineStage] = {}
        self.stage_order: List[str] = []
        self.buffer_size = buffer_size
        self.backpressure_enabled = backpressure_enabled
        self._queues: Dict[str, asyncio.Queue] = {}
        self._running = False
    
    def add_stage(self, name: str, stage: PipelineStage) -> None:
        """Add a stage to the pipeline."""
        self.stages[name] = stage
        self.stage_order.append(name)
        if self.backpressure_enabled:
            self._queues[name] = asyncio.Queue(maxsize=self.buffer_size)
        else:
            self._queues[name] = asyncio.Queue()
    
    async def start(self) -> None:
        """Start all pipeline stages."""
        self._running = True
        for name in self.stage_order:
            await self.stages[name].start()
    
    async def stop(self) -> None:
        """Stop all pipeline stages."""
        self._running = False
        for name in self.stage_order:
            await self.stages[name].stop()
    
    async def process_stream(
        self,
        input_items: AsyncGenerator[T, None],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> AsyncGenerator[PipelineItem[T], None]:
        """
        Process items through the pipeline as a stream.
        
        Args:
            input_items: Async generator of input items
            progress_callback: Called with (stage_name, completed, total)
            
        Yields:
            PipelineItem results as they complete
        """
        await self.start()
        
        # Collect all items first
        items_list = []
        async for item in input_items:
            items_list.append(item)
        
        total_input = len(items_list)
        stage_counts = {name: 0 for name in self.stage_order}
        completed = 0
        
        try:
            if not self.stage_order:
                # No stages, just yield items
                for item in items_list:
                    yield PipelineItem(data=item, stage="complete")
                return
            
            # Simple sequential pipeline: feed all items to first stage
            first_stage = self.stages[self.stage_order[0]]
            for item in items_list:
                await first_stage.put(PipelineItem(data=item, stage="input"))
            
            # Chain stages with simple processing
            if len(self.stage_order) == 1:
                # Single stage - just collect outputs
                final_stage = self.stages[self.stage_order[0]]
                while completed < total_input:
                    try:
                        item = await asyncio.wait_for(final_stage.get(), timeout=2.0)
                        completed += 1
                        if progress_callback:
                            progress_callback(self.stage_order[0], completed, total_input)
                        yield item
                    except asyncio.TimeoutError:
                        if not self._running:
                            break
                        continue
            else:
                # Multi-stage pipeline
                for i in range(len(self.stage_order) - 1):
                    current_stage = self.stages[self.stage_order[i]]
                    next_stage = self.stages[self.stage_order[i + 1]]
                    stage_name = self.stage_order[i]
                    
                    # Transfer from current to next
                    transferred = 0
                    while transferred < total_input:
                        try:
                            item = await asyncio.wait_for(current_stage.get(), timeout=2.0)
                            transferred += 1
                            stage_counts[stage_name] += 1
                            if progress_callback:
                                progress_callback(stage_name, stage_counts[stage_name], total_input)
                            
                            if not item.error:
                                await next_stage.put(item)
                            else:
                                # If it's the last stage, yield error items
                                if i == len(self.stage_order) - 2:
                                    yield item
                        except asyncio.TimeoutError:
                            if not self._running:
                                break
                            continue
                
                # Collect from final stage
                final_stage = self.stages[self.stage_order[-1]]
                while completed < total_input:
                    try:
                        item = await asyncio.wait_for(final_stage.get(), timeout=2.0)
                        completed += 1
                        stage_counts[self.stage_order[-1]] += 1
                        if progress_callback:
                            progress_callback(self.stage_order[-1], completed, total_input)
                        yield item
                    except asyncio.TimeoutError:
                        if not self._running:
                            break
                        continue
        
        finally:
            await self.stop()
    
    async def process_batch(self, items: List[T]) -> List[PipelineItem[T]]:
        """Process a batch of items through the entire pipeline."""
        async def item_generator():
            for item in items:
                yield item
        
        results = []
        async for result in self.process_stream(item_generator()):
            results.append(result)
        return results


# ============================================================================
# Specialized Pipeline Stages
# ============================================================================

class NormalizeStage(PipelineStage[Dict[str, Any]]):
    """Pipeline stage for text normalization."""
    
    def __init__(self, concurrency: int = 5):
        super().__init__("normalize", concurrency)
    
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize text data."""
        # Simulate normalization work
        await asyncio.sleep(0.01)  # Simulate processing time
        
        result = dict(data)
        if 'source_text' in result:
            # Basic normalization
            text = result['source_text']
            # Strip whitespace
            text = text.strip() if text else ""
            # Store normalized
            result['normalized_text'] = text
        
        return result


class TranslateStage(PipelineStage[Dict[str, Any]]):
    """Pipeline stage for async translation."""
    
    def __init__(
        self,
        llm_client: Optional[AsyncLLMClient] = None,
        concurrency: int = 10,
        system_prompt: Optional[str] = None,
    ):
        super().__init__("translate", concurrency)
        self.llm_client = llm_client
        self.system_prompt = system_prompt or "You are a professional translator. Translate the following text from Chinese to Russian."
    
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Translate text using LLM."""
        result = dict(data)
        
        text = data.get('normalized_text') or data.get('source_text', '')
        if not text:
            result['translated_text'] = ""
            return result
        
        if self.llm_client:
            try:
                llm_result = await self.llm_client.chat(
                    system=self.system_prompt,
                    user=text,
                    metadata={"step": "translate", "row_id": data.get('id')},
                )
                result['translated_text'] = llm_result.text
                result['translation_latency_ms'] = llm_result.latency_ms
            except LLMError as e:
                result['translation_error'] = str(e)
                result['translated_text'] = ""
        else:
            # Fallback: mock translation
            result['translated_text'] = f"[Translated] {text[:50]}"
        
        return result


class QAStage(PipelineStage[Dict[str, Any]]):
    """Pipeline stage for quality assurance."""
    
    def __init__(
        self,
        llm_client: Optional[AsyncLLMClient] = None,
        concurrency: int = 8,
        system_prompt: Optional[str] = None,
    ):
        super().__init__("qa", concurrency)
        self.llm_client = llm_client
        self.system_prompt = system_prompt or "Review the following translation for quality issues."
    
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform QA on translated text."""
        result = dict(data)
        
        translated = data.get('translated_text', '')
        if not translated:
            result['qa_passed'] = False
            result['qa_issues'] = ["No translation found"]
            return result
        
        # Simulate or perform QA
        if self.llm_client:
            try:
                qa_prompt = f"Source: {data.get('source_text', '')}\nTranslation: {translated}\n\nCheck for issues."
                llm_result = await self.llm_client.chat(
                    system=self.system_prompt,
                    user=qa_prompt,
                    metadata={"step": "qa", "row_id": data.get('id')},
                )
                # Parse QA response
                result['qa_result'] = llm_result.text
                result['qa_latency_ms'] = llm_result.latency_ms
                # Simple heuristic: if response contains "error" or "issue", mark as failed
                lower_result = llm_result.text.lower()
                result['qa_passed'] = not any(word in lower_result for word in ['error', 'issue', 'problem'])
            except LLMError as e:
                result['qa_error'] = str(e)
                result['qa_passed'] = False
        else:
            # Fallback: mock QA
            result['qa_passed'] = True
            result['qa_issues'] = []
        
        return result


class ExportStage(PipelineStage[Dict[str, Any]]):
    """Pipeline stage for exporting results."""
    
    def __init__(self, output_path: str, concurrency: int = 3):
        super().__init__("export", concurrency)
        self.output_path = output_path
        self.buffer: List[Dict[str, Any]] = []
        self._buffer_lock = asyncio.Lock()
    
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Export processed data."""
        # Add to buffer for batch write
        async with self._buffer_lock:
            self.buffer.append(dict(data))
        
        return data
    
    async def flush(self) -> None:
        """Flush buffer to disk."""
        async with self._buffer_lock:
            if self.buffer:
                await AsyncFileIO.write_csv_async(
                    self.output_path,
                    self.buffer,
                    fieldnames=list(self.buffer[0].keys()) if self.buffer else None
                )


# ============================================================================
# Main Entry Point
# ============================================================================

async def process_csv_async(
    input_path: str,
    output_path: str,
    config: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    llm_client: Optional[AsyncLLMClient] = None,
) -> Dict[str, Any]:
    """
    Main async entry point for processing CSV files.
    
    Implements streaming pipeline:
    1. Read CSV asynchronously
    2. Normalize rows in parallel
    3. Translate with concurrent LLM calls
    4. QA check in parallel
    5. Export results asynchronously
    
    Args:
        input_path: Input CSV file path
        output_path: Output CSV file path
        config: Async configuration dict
        progress_callback: Progress callback (stage, completed, total)
        llm_client: Optional custom LLM client
        
    Returns:
        Dict with processing statistics
    """
    config = config or load_async_config()
    stats = {
        "start_time": datetime.now().isoformat(),
        "input_path": input_path,
        "output_path": output_path,
        "total_rows": 0,
        "processed_rows": 0,
        "failed_rows": 0,
        "stages": {},
    }
    
    # Initialize LLM client if not provided
    if llm_client is None:
        llm_client = AsyncLLMClient(config=config)
    
    async with llm_client:
        # Read input CSV
        _trace({"type": "process_csv_async_start", "input": input_path})
        rows = await AsyncFileIO.read_csv_async(input_path)
        stats["total_rows"] = len(rows)
        
        if not rows:
            stats["end_time"] = datetime.now().isoformat()
            return stats
        
        # Create pipeline
        buffer_size = config.get("buffer_size", 100)
        stage_concurrency = config.get("stage_concurrency", {})
        
        pipeline = AsyncPipeline[Dict[str, Any]](buffer_size=buffer_size)
        pipeline.add_stage("normalize", NormalizeStage(concurrency=stage_concurrency.get("normalize", 5)))
        pipeline.add_stage("translate", TranslateStage(
            llm_client=llm_client,
            concurrency=stage_concurrency.get("translate", 10)
        ))
        pipeline.add_stage("qa", QAStage(
            llm_client=llm_client,
            concurrency=stage_concurrency.get("qa", 8)
        ))
        pipeline.add_stage("export", ExportStage(output_path, concurrency=stage_concurrency.get("export", 3)))
        
        # Process through pipeline
        async def row_generator():
            for row in rows:
                yield row
        
        results = []
        async for item in pipeline.process_stream(row_generator(), progress_callback):
            if item.error:
                stats["failed_rows"] += 1
            else:
                stats["processed_rows"] += 1
            results.append(item.data)
        
        # Final export
        if results:
            await AsyncFileIO.write_csv_async(output_path, results)
        
        stats["end_time"] = datetime.now().isoformat()
        
        # Calculate timing
        start = datetime.fromisoformat(stats["start_time"])
        end = datetime.fromisoformat(stats["end_time"])
        stats["total_duration_seconds"] = (end - start).total_seconds()
        stats["rows_per_second"] = stats["processed_rows"] / max(stats["total_duration_seconds"], 0.001)
    
    _trace({"type": "process_csv_async_complete", "stats": stats})
    return stats


# ============================================================================
# Backward Compatibility
# ============================================================================

def batch_chat(
    prompts: List[Dict[str, Any]],
    max_concurrent: int = 10,
    **kwargs
) -> List[LLMResult]:
    """
    Synchronous wrapper for async batch_chat.
    
    Maintains backward compatibility with existing code.
    
    Args:
        prompts: List of prompt dicts
        max_concurrent: Max concurrent calls
        **kwargs: Additional arguments for AsyncLLMClient
        
    Returns:
        List of LLMResult
    """
    async def _async_batch():
        async with AsyncLLMClient(max_concurrent=max_concurrent, **kwargs) as client:
            results = await client.batch_chat(prompts, max_concurrent=max_concurrent)
            return [r.to_sync_result() for r in results]
    
    return asyncio.run(_async_batch())


# ============================================================================
# Utility Functions
# ============================================================================

async def benchmark_async_vs_sync(
    prompts: List[Dict[str, Any]],
    max_concurrent: int = 10,
) -> Dict[str, Any]:
    """
    Benchmark async vs synchronous processing.
    
    Args:
        prompts: List of prompts to process
        max_concurrent: Max concurrent calls for async
        
    Returns:
        Benchmark results with timing comparison
    """
    from scripts.runtime_adapter import LLMClient
    
    results = {
        "prompt_count": len(prompts),
        "max_concurrent": max_concurrent,
        "sync": {},
        "async": {},
    }
    
    # Test async
    t0 = time.time()
    async with AsyncLLMClient(max_concurrent=max_concurrent) as client:
        async_results = await client.batch_chat(prompts, max_concurrent=max_concurrent)
    async_time = time.time() - t0
    
    results["async"] = {
        "duration_seconds": round(async_time, 3),
        "successful": len([r for r in async_results if r.text]),
        "failed": len([r for r in async_results if not r.text]),
    }
    
    # Test sync (sequential)
    t0 = time.time()
    sync_client = LLMClient()
    sync_results = []
    for prompt in prompts:
        try:
            result = sync_client.chat(
                system=prompt.get("system", ""),
                user=prompt.get("user", ""),
                metadata=prompt.get("metadata"),
            )
            sync_results.append(result)
        except Exception as e:
            sync_results.append(LLMResult(text="", latency_ms=0))
    sync_time = time.time() - t0
    
    results["sync"] = {
        "duration_seconds": round(sync_time, 3),
        "successful": len([r for r in sync_results if r.text]),
        "failed": len([r for r in sync_results if not r.text]),
    }
    
    # Calculate improvement
    if async_time > 0 and sync_time > 0:
        speedup = sync_time / async_time
        improvement = ((sync_time - async_time) / sync_time) * 100
        results["speedup_factor"] = round(speedup, 2)
        results["latency_reduction_percent"] = round(improvement, 1)
    
    return results


# Export public API
__all__ = [
    # Classes
    "AsyncLLMClient",
    "AsyncLLMResult",
    "AsyncPipeline",
    "PipelineStage",
    "PipelineItem",
    "AsyncFileIO",
    "NormalizeStage",
    "TranslateStage",
    "QAStage",
    "ExportStage",
    
    # Functions
    "process_csv_async",
    "batch_chat",
    "load_async_config",
    "benchmark_async_vs_sync",
    
    # Config
    "DEFAULT_ASYNC_CONFIG",
]


# Standalone execution
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Async Game Localization Pipeline")
    parser.add_argument("--input", "-i", required=True, help="Input CSV path")
    parser.add_argument("--output", "-o", required=True, help="Output CSV path")
    parser.add_argument("--max-concurrent", "-c", type=int, default=10, help="Max concurrent LLM calls")
    parser.add_argument("--buffer-size", "-b", type=int, default=100, help="Pipeline buffer size")
    parser.add_argument("--benchmark", action="store_true", help="Run benchmark mode")
    
    args = parser.parse_args()
    
    if args.benchmark:
        # Create test prompts
        test_prompts = [
            {"system": "You are a translator.", "user": f"Translate this text {i}", "metadata": {"step": "translate"}}
            for i in range(20)
        ]
        
        async def run_benchmark():
            results = await benchmark_async_vs_sync(test_prompts, max_concurrent=args.max_concurrent)
            print(json.dumps(results, indent=2))
        
        asyncio.run(run_benchmark())
    else:
        # Run pipeline
        async def run_pipeline():
            def progress(stage, completed, total):
                print(f"[{stage}] {completed}/{total}")
            
            stats = await process_csv_async(
                args.input,
                args.output,
                progress_callback=progress
            )
            print(f"\nCompleted: {stats['processed_rows']}/{stats['total_rows']} rows")
            print(f"Duration: {stats.get('total_duration_seconds', 0):.2f}s")
            print(f"Throughput: {stats.get('rows_per_second', 0):.2f} rows/sec")
        
        asyncio.run(run_pipeline())
