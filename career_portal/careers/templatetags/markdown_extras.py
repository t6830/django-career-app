from django import template
from django.utils.safestring import mark_safe
import markdown2

register = template.Library()

@register.filter(name='markdown_to_html')
def markdown_to_html(markdown_text):
    """
    Converts Markdown text to HTML.
    Uses markdown2 library with extras like 'fenced-code-blocks'.
    """
    if markdown_text is None:
        return ""
    html = markdown2.markdown(str(markdown_text), extras=['fenced-code-blocks', 'tables', 'spoiler', 'lists'])
    # print(html)  # Debugging line to check the HTML output
    return mark_safe(html)
