# knowledge_base/ai_service.py
# WHY a separate module: Keeps AI logic isolated from views.
# If you swap providers (OpenAI → Gemini → local model),
# you only change THIS file. Nothing else needs to know.

import os
import json
import urllib.request
import urllib.error


def generate_post_summary(post) -> str:
    """
    Calls an AI API to generate a concise summary of a post.

    Tries providers in order:
      1. OpenAI GPT-4o-mini  (if OPENAI_API_KEY is set)
      2. Anthropic Claude    (if ANTHROPIC_API_KEY is set)
      3. Fallback            (rule-based local summary — always works, no API needed)

    WHY a fallback: During development you may not have API keys yet.
    The fallback ensures the feature works immediately and degrades
    gracefully rather than crashing.
    """
    openai_key    = os.environ.get('OPENAI_API_KEY')
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')

    if openai_key:
        return _call_openai(post, openai_key)
    elif anthropic_key:
        return _call_anthropic(post, anthropic_key)
    else:
        return _local_fallback_summary(post)


# ─────────────────────────────────────────────────────
# SHARED PROMPT
# WHY a separate constant: Both providers get the EXACT
# same instructions — consistent output regardless of which
# AI is called.
# ─────────────────────────────────────────────────────
def _build_prompt(post) -> str:
    return f"""You are a knowledge management assistant at ACT Fibernet, an internet service provider.

A team member has written the following internal knowledge article. Your task is to write a concise 2-3 sentence summary that:
- Captures the core topic and key takeaway
- Uses plain, professional language
- Is useful as a preview snippet (not a replacement for reading the full article)

Article Title: {post.title}
Category: {post.category.name if post.category else 'General'}

Article Body:
{post.body[:3000]}

Write only the summary. No preamble, no "Here is a summary:", just the summary text itself."""


# ─────────────────────────────────────────────────────
# PROVIDER 1: OpenAI
# ─────────────────────────────────────────────────────
def _call_openai(post, api_key: str) -> str:
    prompt  = _build_prompt(post)
    payload = json.dumps({
        'model': 'gpt-4o-mini',
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 200,
        'temperature': 0.3,  # Low temperature = more factual, less creative
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.openai.com/v1/chat/completions',
        data=payload,
        headers={
            'Content-Type':  'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data['choices'][0]['message']['content'].strip()


# ─────────────────────────────────────────────────────
# PROVIDER 2: Anthropic Claude
# ─────────────────────────────────────────────────────
def _call_anthropic(post, api_key: str) -> str:
    prompt  = _build_prompt(post)
    payload = json.dumps({
        'model': 'claude-haiku-4-5-20251001',  # Fast + cheap for summaries
        'max_tokens': 200,
        'messages': [{'role': 'user', 'content': prompt}],
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=payload,
        headers={
            'Content-Type':      'application/json',
            'x-api-key':         api_key,
            'anthropic-version': '2023-06-01',
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data['content'][0]['text'].strip()


# ─────────────────────────────────────────────────────
# FALLBACK: Rule-based local summary (no API needed)
# WHY: Lets you develop and test without burning API credits.
# Also useful as a safety net if the API is down.
# ─────────────────────────────────────────────────────
def _local_fallback_summary(post) -> str:
    # Split body into sentences, take first 2-3
    import re
    sentences = re.split(r'(?<=[.!?])\s+', post.body.strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    summary_sentences = sentences[:3]

    if not summary_sentences:
        return f"This article covers: {post.title}."

    summary = ' '.join(summary_sentences)
    if len(summary) > 400:
        summary = summary[:400].rsplit(' ', 1)[0] + '...'

    return summary


   