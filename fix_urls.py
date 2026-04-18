# fix_urls.py
import os

# Get the templates directory
templates_dir = 'knowledge_base/templates/knowledge_base/'

# List of replacements
replacements = [
    ("{% url 'post_list'", "{% url 'knowledge_base:post_list'"),
    ("{% url 'post_create'", "{% url 'knowledge_base:post_create'"),
    ("{% url 'post_detail'", "{% url 'knowledge_base:post_detail'"),
    ("{% url 'dashboard'", "{% url 'knowledge_base:dashboard'"),
    ("{% url 'login'", "{% url 'knowledge_base:login'"),
    ("{% url 'logout'", "{% url 'knowledge_base:logout'"),
    ("{% url 'register'", "{% url 'knowledge_base:register'"),
    ("{% url 'profile'", "{% url 'knowledge_base:profile'"),
    ("{% url 'my_workspace'", "{% url 'knowledge_base:my_workspace'"),
    ("{% url 'approval_queue'", "{% url 'knowledge_base:approval_queue'"),
    ("{% url 'pending_comments'", "{% url 'knowledge_base:pending_comments'"),
    ("{% url 'search'", "{% url 'knowledge_base:search'"),
    ("{% url 'user_list'", "{% url 'knowledge_base:user_list'"),
    ("{% url 'add_comment'", "{% url 'knowledge_base:add_comment'"),
    ("{% url 'post_upvote'", "{% url 'knowledge_base:post_upvote'"),
    ("{% url 'toggle_comment_approval'", "{% url 'knowledge_base:toggle_comment_approval'"),
    ("{% url 'bulk_comment_action'", "{% url 'knowledge_base:bulk_comment_action'"),
    ("{% url 'post_edit'", "{% url 'knowledge_base:post_edit'"),
    ("{% url 'post_submit'", "{% url 'knowledge_base:post_submit'"),
    ("{% url 'post_approve'", "{% url 'knowledge_base:post_approve'"),
    ("{% url 'post_reject'", "{% url 'knowledge_base:post_reject'"),
    ("{% url 'analytics_dashboard'", "{% url 'knowledge_base:analytics_dashboard'"),
]

# Process all HTML files
for filename in os.listdir(templates_dir):
    if filename.endswith('.html'):
        filepath = os.path.join(templates_dir, filename)
        print(f"Processing {filename}...")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply all replacements
        for old, new in replacements:
            content = content.replace(old, new)
        
        # Write back if changed
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✓ Updated {filename}")
        else:
            print(f"  - No changes in {filename}")

print("\n✓ All templates updated!")