#!/usr/bin/env bash
# download_qingdan.sh - Download 工程量清单.pdf from cqggzy.com
# Priority: 答疑补遗 → 招标公告 (fallback)
# Usage: download_qingdan.sh <clarify_url> [bid_announcement_url]
#   - First argument: 答疑补遗 page URL (required)
#   - Second argument: 招标公告 page URL (optional fallback)
# Requires: curl, grep
# Output: Downloads PDF to /tmp/project_qingdan.pdf

set -e

CLARIFY_URL="$1"
BID_URL="$2"

if [ -z "$CLARIFY_URL" ]; then
    echo "Usage: $0 <clarify_url> [bid_announcement_url]"
    echo "  Downloads 工程量清单.pdf from cqggzy.com"
    echo "  Priority: 答疑补遗 → 招标公告 (fallback)"
    exit 1
fi

TMPDIR="/tmp/cqggzy_$$"
mkdir -p "$TMPDIR"
PDF_SAVED=""

# Try downloading attachment from a given page URL
# Arguments: $1 = page URL, $2 = label for logging
# Returns: 0 if PDF downloaded, 1 if no attachment found
try_download() {
    local PAGE_URL="$1"
    local LABEL="$2"
    local PAGE_FILE="$TMPDIR/page_$$.html"

    echo ">>> Trying $LABEL: $PAGE_URL"

    # Download the page
    curl -sL --connect-timeout 15 -c "$TMPDIR/cookies.txt" "$PAGE_URL" > "$PAGE_FILE" 2>&1 || {
        echo "Warning: Failed to download $LABEL page"
        return 1
    }

    # Extract attachment GUID and Code
    local GUID CODE
    GUID=$(grep -oP "downloadAttach\('\K[^']+" "$PAGE_FILE" | head -1)
    CODE=$(grep -oP "downloadAttach\('[^']+','\K[^']+" "$PAGE_FILE" | head -1)

    if [ -z "$GUID" ]; then
        echo "  No attachment found on $LABEL page"
        return 1
    fi

    echo "  Found attachment: GUID=$GUID Code=${CODE:-J080}"

    # Download the PDF
    local DOWNLOAD_URL="https://ggzydl.cqggzy.com/CQTPBidder/jsgcztbmis2/pages/zbfilelingqu_hy/cQZBFileDownAttachAction.action?cmd=download&AttachGuid=${GUID}&FileCode=${CODE:-J080}&ClientGuid=$(uuidgen 2>/dev/null || echo '631ba536-309c-405c-8c7e-8650a5bac8f8')"
    curl -sL --connect-timeout 30 -b "$TMPDIR/cookies.txt" -e "$PAGE_URL" -o "$TMPDIR/qingdan.pdf" "$DOWNLOAD_URL" 2>&1

    # Verify
    local SIZE
    SIZE=$(wc -c < "$TMPDIR/qingdan.pdf" 2>/dev/null || echo 0)
    if [ "$SIZE" -lt 1000 ]; then
        echo "  Downloaded file too small ($SIZE bytes), might be invalid"
        return 1
    fi

    echo "  Downloaded PDF: $(file "$TMPDIR/qingdan.pdf" | cut -d: -f2-)"
    echo "  Size: $SIZE bytes"
    PDF_SAVED="$TMPDIR/qingdan.pdf"
    return 0
}

# Try clarify page first
if try_download "$CLARIFY_URL" "答疑补遗"; then
    : # PDF downloaded successfully
elif [ -n "$BID_URL" ] && try_download "$BID_URL" "招标公告"; then
    : # PDF downloaded from fallback
else
    echo "ERROR: No 工程量清单.pdf found on either page."
    echo "  Tried:"
    echo "    1. 答疑补遗: $CLARIFY_URL"
    [ -n "$BID_URL" ] && echo "    2. 招标公告: $BID_URL"
    rm -rf "$TMPDIR"
    exit 1
fi

# Copy to standard location
cp "$PDF_SAVED" /tmp/project_qingdan.pdf
echo ""
echo "=== Success ==="
echo "PDF saved to /tmp/project_qingdan.pdf"
echo "Also available at: $PDF_SAVED"
