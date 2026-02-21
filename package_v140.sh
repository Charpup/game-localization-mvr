#!/bin/bash
# Package loc-mVR v1.4.0

VERSION="1.4.0"
SKILL_NAME="loc-mvr-${VERSION}"

echo "📦 Packaging ${SKILL_NAME}..."

cd skill/v1.4.0

# Create tarball
tar -czf "../../skill/${SKILL_NAME}.skill.tar.gz" \
    SKILL.md \
    scripts/ \
    lib/ \
    config/ \
    references/ \
    examples/ \
    assets/

cd ../..

# Generate checksum
sha256sum "skill/${SKILL_NAME}.skill.tar.gz" > "skill/${SKILL_NAME}.skill.tar.gz.sha256"

echo "✅ Packaged: skill/${SKILL_NAME}.skill.tar.gz"
echo "📊 Size: $(du -h skill/${SKILL_NAME}.skill.tar.gz | cut -f1)"
