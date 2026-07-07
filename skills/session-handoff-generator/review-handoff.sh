#!/usr/bin/env bash
#
# Session Handoff Review Workflow
#
# Interactive review of draft handoff artifacts.
# Prompts user to keep/delete/edit/defer each item.
#
# Usage: ./review-handoff.sh <handoff-file.md>
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <handoff-file.md>"
    echo ""
    echo "Example:"
    echo "  $0 memory/handoffs/2026-07-07-ffdc78df.md"
    exit 1
fi

HANDOFF_FILE="$1"

if [ ! -f "$HANDOFF_FILE" ]; then
    echo -e "${RED}Error: File not found: ${HANDOFF_FILE}${NC}"
    exit 1
fi

echo -e "${BLUE}=== Session Handoff Review ===${NC}"
echo -e "File: ${HANDOFF_FILE}"
echo -e "Date: $(date '+%Y-%m-%d %H:%M')"
echo ""

# Extract metadata from frontmatter
SESSION_ID=$(grep -E '^\*\*Session:\*\*' "$HANDOFF_FILE" | sed 's/.*: \*\?\([^*]*\)\*\?.*/\1/' | tr -d ' ')
CREATED_AT=$(grep -E '^\*\*Created:\*\*' "$HANDOFF_FILE" | sed 's/.*: \*\?\([^*]*\)\*\?.*/\1/' | tr -d ' ')
EXPIRES_AT=$(grep -E '^\*\*Expires:\*\*' "$HANDOFF_FILE" | sed 's/.*: \*\?\([^*]*\)\*\?.*/\1/' | tr -d ' ')

echo -e "${YELLOW}Session:${NC} ${SESSION_ID:-N/A}"
echo -e "${YELLOW}Created:${NC} ${CREATED_AT:-N/A}"
echo -e "${YELLOW}Expires:${NC} ${EXPIRES_AT:-N/A}"
echo ""

# Temporary files for tracking decisions
APPROVED_FILE=$(mktemp)
REJECTED_FILE=$(mktemp)
EDITED_FILE=$(mktemp)
DEFERRED_FILE=$(mktemp)

cleanup() {
    rm -f "$APPROVED_FILE" "$REJECTED_FILE" "$EDITED_FILE" "$DEFERRED_FILE"
}
trap cleanup EXIT

# Function to display and prompt for an item
review_item() {
    local kind="$1"
    local number="$2"
    local text="$3"
    local confidence="$4"
    local source="$5"
    local reason="$6"
    
    echo -e "${BLUE}─────────────────────────────────────${NC}"
    echo -e "${YELLOW}[$kind]${NC} #$number"
    echo ""
    echo -e "${GREEN}Text:${NC} $text"
    echo -e "${YELLOW}Confidence:${NC} $confidence"
    echo -e "${YELLOW}Source:${NC} $source"
    echo -e "${YELLOW}Reason:${NC} $reason"
    echo ""
    echo -e "Actions: ${GREEN}[k]eep${NC}  ${RED}[d]elete${NC}  ${BLUE}[e]dit${NC}  ${YELLOW}[s]kip${NC} (defer decision)"
    echo -n "> "
    
    read -r choice
    
    case $choice in
        k|K|keep)
            echo "$kind|$text|$confidence|$source|$reason" >> "$APPROVED_FILE"
            echo -e "${GREEN}✓ Approved${NC}"
            ;;
        d|D|delete|reject)
            echo "$kind|$text|$confidence|$source|$reason" >> "$REJECTED_FILE"
            echo -e "${RED}✗ Rejected${NC}"
            ;;
        e|E|edit)
            echo -e "${BLUE}Enter edited text (empty line to finish):${NC}"
            edited_text=""
            while IFS= read -r line; do
                if [ -z "$line" ]; then
                    break
                fi
                edited_text+="$line "
            done
            
            if [ -n "$edited_text" ]; then
                echo "$kind|$edited_text|$confidence|$source|$reason (edited)" >> "$EDITED_FILE"
                echo -e "${GREEN}✓ Edited and approved${NC}"
            else
                echo -e "${YELLOW}⊘ No changes made, skipping${NC}"
                echo "$kind|$text|$confidence|$source|$reason" >> "$DEFERRED_FILE"
            fi
            ;;
        s|S|skip|defer)
            echo -e "${YELLOW}⊘ Deferred${NC}"
            echo "$kind|$text|$confidence|$source|$reason" >> "$DEFERRED_FILE"
            ;;
        *)
            echo -e "${RED}Invalid choice, deferring item${NC}"
            echo "$kind|$text|$confidence|$source|$reason" >> "$DEFERRED_FILE"
            ;;
    esac
    
    echo ""
}

# Parse markdown file and extract items
# This is a simplified parser - assumes consistent markdown structure

echo -e "${BLUE}Processing Carry Forward items...${NC}"
echo ""

# Extract carry forward items using awk
awk '
    /^## Carry Forward/ { in_section=1; next }
    /^## / { in_section=0 }
    in_section && /^### / { 
        gsub(/^### [0-9]+\. \[/, "")
        gsub(/\].*/, "")
        kind=$0
    }
    in_section && /^\*\*Text:\*\*/ { 
        gsub(/^\*\*Text:\*\* /, "")
        text=$0
    }
    in_section && /^\*\*Confidence:\*\*/ { 
        gsub(/^\*\*Confidence:\*\* /, "")
        confidence=$0
    }
    in_section && /^\*\*Source:\*\*/ { 
        gsub(/^\*\*Source:\*\* Turn /, "Turn ")
        source=$0
    }
    in_section && /^\*\*Reason:\*\*/ { 
        gsub(/^\*\*Reason:\*\* /, "")
        reason=$0
        print kind "|" text "|" confidence "|" source "|" reason
    }
' "$HANDOFF_FILE" | while IFS='|' read -r kind text confidence source reason; do
    if [ -n "$kind" ] && [ -n "$text" ]; then
        review_item "$kind" "CF" "$text" "$confidence" "$source" "$reason"
    fi
done

echo -e "${BLUE}Processing Unresolved Tensions...${NC}"
echo ""

awk '
    /^## Unresolved Tensions/ { in_section=1; next }
    /^## / { in_section=0 }
    in_section && /^### / { 
        gsub(/^### [0-9]+\. /, "")
        text=$0
    }
    in_section && /^\*\*Confidence:\*\*/ { 
        gsub(/^\*\*Confidence:\*\* /, "")
        confidence=$0
    }
    in_section && /^\*\*Source:\*\*/ { 
        gsub(/^\*\*Source:\*\* Turn /, "Turn ")
        source=$0
    }
    in_section && /^\*\*Reason:\*\*/ { 
        gsub(/^\*\*Reason:\*\* /, "")
        reason=$0
        print "unresolved-tension|" text "|" confidence "|" source "|" reason
    }
' "$HANDOFF_FILE" | while IFS='|' read -r kind text confidence source reason; do
    if [ -n "$kind" ] && [ -n "$text" ]; then
        review_item "$kind" "UT" "$text" "$confidence" "$source" "$reason"
    fi
done

echo -e "${BLUE}Processing User Corrections...${NC}"
echo ""

awk '
    /^## User Corrections/ { in_section=1; next }
    /^## / { in_section=0 }
    in_section && /^### / { 
        gsub(/^### [0-9]+\. /, "")
        text=$0
    }
    in_section && /^\*\*Confidence:\*\*/ { 
        gsub(/^\*\*Confidence:\*\* /, "")
        confidence=$0
    }
    in_section && /^\*\*Source:\*\*/ { 
        gsub(/^\*\*Source:\*\* Turn /, "Turn ")
        source=$0
    }
    in_section && /^\*\*Reason:\*\*/ { 
        gsub(/^\*\*Reason:\*\* /, "")
        reason=$0
        print "correction|" text "|" confidence "|" source "|" reason
    }
' "$HANDOFF_FILE" | while IFS='|' read -r kind text confidence source reason; do
    if [ -n "$kind" ] && [ -n "$text" ]; then
        review_item "$kind" "UC" "$text" "$confidence" "$source" "$reason"
    fi
done

# Generate summary
echo -e "${BLUE}═══════════════════════════════════${NC}"
echo -e "${BLUE}Review Summary${NC}"
echo -e "${BLUE}═══════════════════════════════════${NC}"
echo ""

approved_count=$(wc -l < "$APPROVED_FILE" 2>/dev/null || echo 0)
rejected_count=$(wc -l < "$REJECTED_FILE" 2>/dev/null || echo 0)
edited_count=$(wc -l < "$EDITED_FILE" 2>/dev/null || echo 0)
deferred_count=$(wc -l < "$DEFERRED_FILE" 2>/dev/null || echo 0)

echo -e "${GREEN}Approved:${NC} $approved_count"
echo -e "${RED}Rejected:${NC} $rejected_count"
echo -e "${BLUE}Edited:${NC} $edited_count"
echo -e "${YELLOW}Deferred:${NC} $deferred_count"
echo ""

# Update handoff file with review results
if [ $approved_count -gt 0 ] || [ $edited_count -gt 0 ]; then
    NEW_STATE="user-reviewed"
    if [ $edited_count -gt 0 ]; then
        NEW_STATE="edited"
    fi
    
    # Update consent state in file
    sed -i.bak "s/\*\*Consent State:\*\* .*/\*\*Consent State:\*\* ${NEW_STATE}/" "$HANDOFF_FILE"
    rm -f "${HANDOFF_FILE}.bak"
    
    # Add reviewed timestamp
    REVIEWED_AT=$(date -Iseconds)
    sed -i.bak "/^\*\*Consent State:\*\*/a\\
**Reviewed At:** ${REVIEWED_AT}" "$HANDOFF_FILE"
    rm -f "${HANDOFF_FILE}.bak"
    
    echo -e "${GREEN}✓ Handoff updated to: ${NEW_STATE}${NC}"
else
    echo -e "${YELLOW}⊘ No items approved, handoff remains in draft state${NC}"
fi

# Commit corrections to corrections log
if [ -s "$APPROVED_FILE" ] || [ -s "$EDITED_FILE" ]; then
    echo ""
    echo -e "${YELLOW}Committing approved corrections to memory/corrections-log.md...${NC}"
    
    # Append approved corrections to log
    grep "^correction|" "$APPROVED_FILE" "$EDITED_FILE" 2>/dev/null | while IFS='|' read -r kind text confidence source reason; do
        cat >> memory/corrections-log.md << EOF

## $(date +%Y-%m-%d) — Correction from Session ${SESSION_ID}

| Field | Value |
|-------|-------|
| **What was wrong** | See session transcript |
| **Correction** | ${text} |
| **Source** | Session ${SESSION_ID}, ${source} |
| **Status** | ✅ Fixed (approved via handoff review) |
| **Regression Test** | ctx_007 (corrections log consulted) |
| **Notes** | ${reason} |

EOF
    done
    
    echo -e "${GREEN}✓ Corrections committed${NC}"
fi

# Show deferred items
if [ -s "$DEFERRED_FILE" ]; then
    echo ""
    echo -e "${YELLOW}Deferred items (will remain in draft):${NC}"
    cat "$DEFERRED_FILE"
fi

echo ""
echo -e "${BLUE}Review complete.${NC}"
echo -e "Updated handoff: ${HANDOFF_FILE}"
echo -e ""
echo -e "Next steps:"
echo -e "  - Approved items will be injected into next session bootstrap"
echo -e "  - Corrections logged to memory/corrections-log.md"
echo -e "  - Deferred items remain in draft for future review"
