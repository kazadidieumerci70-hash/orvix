"""Keep recent dialogue within a character budget, without stored source blobs."""
import json
import re


def conversation_context(history, max_chars: int = 24000) -> str:
    blocks = []
    remaining = max_chars
    for message in reversed(history[-60:]):
        content = re.sub(r'\[\[ORVIX_SOURCE\]\].*?\[\[/ORVIX_SOURCE\]\]', '', message.content, flags=re.S).strip()
        # JSON preserves role boundaries even when user text includes role labels.
        if not content:
            continue
        block = json.dumps({'role': message.role, 'content': content}, ensure_ascii=False)
        if len(block) + 1 > remaining:
            if not blocks and remaining > 100:
                # Oversized latest message: retain both its beginning and ending.
                size = max(1, (remaining - 100) // 4)
                block = json.dumps({'role': message.role, 'content': content[:size] + '\n[Message abrégé]\n' + content[-size:]}, ensure_ascii=False)
                if len(block) <= remaining:
                    blocks.append(block)
            break
        blocks.append(block)
        remaining -= len(block) + 1
    return '\n'.join(reversed(blocks))
