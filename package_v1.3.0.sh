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
cp skill/v${VERSION}/SKILL.md "skill/v${VERSION}/"

# Create requirements.txt if not exists
if [ ! -f "requirements.txt" ]; then
    echo "# Loc-MVR v${VERSION} Dependencies" > "skill/v${VERSION}/requirements.txt"
    echo "# Python 3.11+ required" >> "skill/v${VERSION}/requirements.txt"
    echo "# See pyproject.toml or setup.py for full dependencies" >> "skill/v${VERSION}/requirements.txt"
fi

# Create skill archive
tar -czf "skill/${SKILL_NAME}.skill.tar.gz" -C "skill/v${VERSION}" .

echo "✅ Skill packaged: skill/${SKILL_NAME}.skill.tar.gz"
echo "📊 Archive contents:"
tar -tzf "skill/${SKILL_NAME}.skill.tar.gz" | head -20
echo "..."
