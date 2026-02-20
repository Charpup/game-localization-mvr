#!/bin/bash
# Package loc-mVR v1.3.0 as OpenClaw skill

VERSION="1.3.0"
SKILL_NAME="loc-mvr-${VERSION}"

echo "📦 Packaging ${SKILL_NAME}..."

# Create skill directory
mkdir -p "skill/v${VERSION}"

# Copy core files
cp -r src/scripts "skill/v${VERSION}/"
cp -r src/config "skill/v${VERSION}/"
cp SKILL.md "skill/v${VERSION}/"
cp requirements.txt "skill/v${VERSION}/" 2>/dev/null || true

# Create skill archive
tar -czf "skill/${SKILL_NAME}.skill.tar.gz" -C "skill/v${VERSION}" .

echo "✅ Skill packaged: skill/${SKILL_NAME}.skill.tar.gz"
