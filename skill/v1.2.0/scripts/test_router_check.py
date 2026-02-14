from runtime_adapter import LLMClient
import os
import json

def test_router():
    print("Testing Router Batch Enforcement...")
    client = LLMClient()
    
    # Test 1: gpt-4.1 (unfit) + is_batch=True -> Should switch
    print("\nTest 1: gpt-4.1 (unfit) + is_batch=True")
    try:
        res = client.chat(
            system="system", 
            user="user", 
            metadata={"is_batch": True, "model_override": "gpt-4.1"}
        )
        # Check trace for "router_batch_enforcement" or check used model
        # The result object doesn't expose 'model' directly but we can infer from logs or if we added it to result
        print("Call completed.")
    except Exception as e:
        print(f"Call failed: {e}")

    # Test 2: gpt-4.1-mini (ok) + is_batch=True -> Should stay
    print("\nTest 2: gpt-4.1-mini (ok) + is_batch=True")
    try:
        res = client.chat(
            system="system", 
            user="user", 
            metadata={"is_batch": True, "model_override": "gpt-4.1-mini"}
        )
        print("Call completed.")
    except Exception as e:
        print(f"Call failed: {e}")

if __name__ == "__main__":
    test_router()
