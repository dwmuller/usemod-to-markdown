#!/usr/bin/env python

"""
Converts UseMod wiki pages to markdown files .

TODO: 
* Front matter, once I know what I want.
* More options should come from command line. (base URL, debugging)
* trailing slash on page URLs should be optional
* read UseMod config file?

"""

# Standard packages
import datetime
import io
import re
import sys
from urllib.parse import urlparse

# Additional packages
import yaml

# options
overwrite_outputs = False
debug_format = False
supress_msgs = False
page_link_suffix = "/"
page_link_prefix = "../"
page_links_relative = None
home_page = 'HomeWiki'
html_allowed = True  # Markdown target allows embedded HTML

# Selected UseMod wiki config options.
UseSubpage  = True  # Allow subpages
FreeUpper   = True  # Force uppercase in page name words
RawHtml     = True  # Allow <html> regions (default False)
HtmlTags    = True  # Allow unsafe HTML tags (default False)
HtmlLinks   = False # Allow raw HTML links
FreeLinks   = True  # Allow double-bracket page links
SimpleLinks = False # Allow only letters in page names
NetworkFile = True  # Allow file: links
BracketText = True  # Allow [url link-text]
WikiLinks   = False # Allow LinkPattern (otherwise use [[page]] only) (default True)
BracketWiki = False # Allow text in [WikiLnk txt]
UseHeadings = True  # Allow headings

# Markers used to separate data in UseMod database files.
FS = "\xb3"
FS1 = FS + "1"
FS2 = FS + "2"
FS3 = FS + "3"

# Global data
intermap = {}
intermap_prefix = ''

def usemod_pages_to_markdown_files(input_dir, output_dir):

    read_intermap(input_dir)

    for letter_dir in (input_dir / 'page').resolve().iterdir():
        if letter_dir.is_dir():
            for page_item in letter_dir.iterdir():
                if page_item.is_file():
                    convert_page_file(page_item, output_dir)
                elif page_item.is_dir() & UseSubpage:
                    for subpage_item in page_item.iterdir():
                        subpage_output_dir = output_dir / page_item.name
                        subpage_output_dir.mkdir(parents=True, exist_ok=True)
                        convert_page_file(subpage_item, subpage_output_dir)

def read_intermap(input_dir):
    global intermap
    global intermap_prefix
    intermap = {}
    with open((input_dir / 'intermap').resolve()) as fh:
        for line in fh:
            key, url = line.strip().split(' ', 1)
            intermap[key] = url
    if not 'LocalWiki' in intermap:
        intermap['LocalWiki'] = page_link_prefix
    if not 'Local' in intermap:
        intermap['Local'] = page_link_prefix
    intermap_prefix = f'(P<intermap_key>{"|".join(intermap)}):'

def read_config(file):
    items = [
        "UseSubpage",
        "FreeUpper",
        "RawHtml",
        "HtmlTags",
        "HtmlLinks",
        "FreeLinks",
        "SimpleLinks",
        "NetworkFile",
        "BracketText",
        "WikiLinks",
        "BracketWiki",
        "UseHeadings"
    ]
    with open(file) as fh:
        for line in fh:
            m = re.match(rf'\$({"|".join(items)})\s*=\s*("?)(.*?);\2', line)
            if m:
                option = m[1]
                value = m[3]
                # All the options we use right now are Boolean, making this
                # rather simple.
                globals()[option] = value == "1"

def convert_page_file(file, output_dir):
    if not supress_msgs: print (f'Converting file {file}')

    parent_id = None
    if file.parent.parent.name != 'page':
        parent_id = file.parent.name

    contents = open(file, encoding='cp1252').read()
    #print contents

    page = usemod_data_to_dictionary(contents, FS1)

    section = usemod_data_to_dictionary(page['text_default'], FS2)

    timestamp = section['ts']
    dt = datetime.datetime.fromtimestamp(float(timestamp))

    data = usemod_data_to_dictionary(section['data'], FS3)
    text = data['text']
    page_id = file.stem
    markdown_text = usemod_page_to_markdown(text, page_id, parent_id)

    if output_dir is None:
        out_fh = sys.stdout
    else:
        output_file = f'{page_id}.md'
        filename = sys.stdout if output_dir is None else (output_dir / output_file).resolve()
        if not overwrite_outputs and filename.exists():
            print(f'WARNING: Output file exists, will not overwrite: {filename}')
            return
        out_fh = io.open(filename, 'w', encoding='utf-8')
    write_post(out_fh, parent_id, page_id, dt, markdown_text)

def usemod_data_to_dictionary(buf, fs):
    s = buf.split(fs)
    keys = s[::2]
    vals = s[1::2]
    assert len(keys) == len(vals)
    return dict(list(zip(keys, vals)))

def write_post(out_fh, parent_id, page_id, dt, txt):
    page_title = page_id.replace('_',' ') if FreeLinks else page_id
    if parent_id and FreeLinks:
        parent_title = re.sub('_', ' ', parent_id)
        page_title = f'{parent_id}/{page_title}'
    frontmatter = {
        'title': page_title,
        'date': dt.isoformat()
    }
    # We add a parent only for sub-pages.
    if parent_id:
        frontmatter['wiki_parent'] = parent_title

    out_fh.write('---\n')
    yaml.dump(frontmatter, out_fh, default_flow_style=False)
    out_fh.write('---\n\n')

    out_fh.write(txt)
    out_fh.close()

# Pattern helpers

### Regular expression pattern fragments, mostly initialized dynamically:

## Tags allowed if HtmlTags is true. Not particularly safe.
html_single_pattern = 'br|p|hr|li|dt|dd|tr|td|th'
html_pairs_pattern = html_single_pattern + '|b|i|u|font|big|small|sub|sup|h1|h2|h3|h4|h5|h6|cite|code|em|s|strike|strong|tt|var|div|center|blockquote|ol|ul|dl|table|caption'

## Link patterns
free_link_pattern = None
link_pattern = None
url_pattern = None
inter_link_pattern = None
anchored_link_pattern = None

# Set up link patterns, which can vary based on options.
def init_link_patterns():
    global free_link_pattern
    global link_pattern
    global url_pattern
    global inter_link_pattern
    global anchored_link_pattern

    upper_letter = '[A-Z]'
    lower_letter = '[a-z]'
    any_letter = '[A-Za-z' + (']' if SimpleLinks else '_0-9]')
    # Main link pattern: lower between upper, then anything
    page_name = f'{upper_letter}+{lower_letter}+{upper_letter}{any_letter}*'
    # Optional subpage link pattern: upper, lower, then anything
    subpage_name = f'{upper_letter}+{lower_letter}+{any_letter}*'
    if UseSubpage:
        # Loose pattern: If subpage , it may be simple
        link_pattern = fr"((?:(?:{page_name})?\\/{subpage_name})|{page_name})"
    else:
        link_pattern = f'{page_name}'
    quote_delim = '(?:"")?' # Optional quote delimiter - have never seen this used.
    anchored_link_pattern = fr'{link_pattern}#(\w+){quote_delim}'
    link_pattern = link_pattern + quote_delim
    inter_site_pattern = f'{upper_letter}{any_letter}+'
    inter_link_pattern = fr'((?:{inter_site_pattern}:[^\]\s"<>{FS}]+){quote_delim})'
    if FreeLinks:
        any_letter = "[-,.()' _0-9A-Za-z]"
    if UseSubpage:
        free_link_pattern = fr'((?:(?:{any_letter}+)?/)?{any_letter}+){quote_delim}'
    else:
        free_link_pattern = fr'({any_letter}+){quote_delim}'
    url_protocols = 'https?|ftp|afs|news|nntp|mid|cid|mailto|wais|prospero|telnet|gopher'
    if NetworkFile:
        url_protocols = url_protocols + '|file'
    url_pattern = rf'((?:(?:{url_protocols}):[^\]\s"<>{FS}]+){quote_delim})'
    image_extensions = '(gif|jpg|png|bmp|jpeg)'
    rfc_pattern = r'RFC\s?(\d+)'
    isbn_pattern = r'ISBN:?([0-9- xX]{`0,})'
    upload_pattern = rf'upload:([^\]\s"<>{FS}]+){quote_delim}'


def usemod_page_to_markdown(text, page_id, parent_id):

    # For UseMod constructs, see:
    # - http://www.usemod.com/cgi-bin/wiki.pl?TextFormattingExamples
    # - http://www.usemod.com/cgi-bin/wiki.pl?TextFormattingRules
    #
    # Also see the UseMod Perl code itself. Used heavily for algorithm
    # inspiration.
    #
    # For Markdown constructs, see:
    # - https://www.markdownguide.org/
    #
    # Order of transformations is significant, otherwise some translated
    # formatting will erroneously trigger later transformations. This could be
    # alleviated by introducing a temporary marker for translated constructs.
    #
    # Some deliberately unsupported UseMod constructs
    # named anchors (<a name=''>)
    # <tt>

    last_bracket_url_index = 0 # Counter for numbered reference links.
    indexed_bracket_urls = {}

    last_chunk_index = -1
    saved_markdown_chunks = []

    def make_marker(n):
        return f'{FS}{n}{FS}'

    def get_bracket_index(url):
        nonlocal last_bracket_url_index
        nonlocal indexed_bracket_urls
        i = indexed_bracket_urls.get(url)
        if i is None:
            last_bracket_url_index = last_bracket_url_index + 1
            indexed_bracket_urls[url] = last_bracket_url_index
            i = last_bracket_url_index
        return f'{i}'
    def get_text_or_bracket_index(ref, text):
        if text is None:
            return get_bracket_index(ref)
        else:
            return text.strip()

    def store_raw(html):
        nonlocal last_chunk_index
        nonlocal saved_markdown_chunks
        last_chunk_index = last_chunk_index + 1
        saved_markdown_chunks.append(html)
        return make_marker(last_chunk_index)

    def restore_chunks(txt):
        nonlocal last_chunk_index
        nonlocal saved_markdown_chunks
        for i in range(last_chunk_index, -1, -1):
            marker = make_marker(i)
            value = saved_markdown_chunks[i]
            if debug_format: print (f'!restoring {marker} => {value}')
            def quoted_replacement(m):
                return value # Prevents backslash-processing.
            txt = re.sub(marker, quoted_replacement, txt, count=1, flags=re.ASCII)
        return txt


    def store_markdown_link(url, link_text = None):
        if link_text is None:
            return store_raw(f'<{url}>')
        else:
            return store_raw(f'[{link_text}]({url})')
    def store_link_or_image(url, link_text = None):
        # TODO: images.
        return store_markdown_link(url, link_text)

    def transform_pre(m):
        tag = m[1]
        txt = m[2]
        if debug_format: print(f'!pre({tag})')
        return store_raw(f'<{tag}>{txt}</{tag}>')
    def transform_raw(m):
        if debug_format: print(f'!raw')
        return store_raw(m[1])
    def transform_html_link(m):
        # <A attributes>link_text</A>
        attr_text = m[1]
        link_text = m[2]
        if debug_format: print(f'!html_link("{attr_text}","{link_text}")')
        quotes = '"|\''
        attrs = attr_text.findall(rf'(\w+)=({quotes})(.*?)\2')
        if len(attrs) == 1 and attrs[0][0].upper == 'HREF':
            url = attrs[0]
            return store_markdown_link(url, link_text)
        # Store it unmodified and hope that the Markdown processer can handle
        # the naked HTML.
        return store_markdown_link(m[0])
    def transform_free_link(m):
        # [[PageRef]], [[PageRef text]]
        nonlocal parent_id
        page_ref = m[1]
        link_text = m[2] if m.lastindex > 1 else None
        if debug_format: print (f'!free_link("{page_ref}", "{link_text}")')
        if link_text is None:
            link_text = page_ref
        else:
            link_text = link_text.strip()
        # trim extra spaces
        page_ref = page_ref.strip()
        page_ref = re.sub(r'\s*/\s*','/', page_ref) # around subpage delim
        url, link_text = page_ref_to_link_parts(page_ref, None, link_text, page_id, parent_id)
        return store_markdown_link(url, link_text)
    def transform_bracket_url(m):
        # [url], [url text]
        url = m[1]
        link_text = m[2] if m.lastindex > 1 else None
        if debug_format: print(f'!bracket_url("{url}", "{link_text}")')
        if link_text is None:
            link_text = get_bracket_index(url)
        else:
            link_text = f'[{link_text.strip()}]'
        return store_markdown_link(url, link_text)
    def transform_bracket_interlink(m):
        # [InterSite:path], [InterSite:path text]
        interlink = m[1]
        link_text = m[2] if m.lastindex > 1 else None
        if debug_format: print(f'!interlink("{interlink}","{link_text}")')
        url = get_interlink_url(interlink)
        if url is None:
            return m[0] # Can't translate it, leave it alone, could be a misfire.
        if link_text is None:
            link_text = get_bracket_index(interlink)
        else:
            link_text = f'[{link_text.strip()}]'
        return store_markdown_link(url, link_text)
    def transform_bracket_link(m):
        # [PageRef], [PageRef text]
        page_ref = m[1]
        link_text = m[2]
        if debug_format: print(f'!bracket_link("{page_ref}", "{link_text}")')
        url, link_text = page_ref_to_link_parts(page_ref, None, f'[{link_text}]', page_id, parent_id)
        return store_markdown_link(url, link_text)
    def transform_bracket_anchored_link(m):
        #  [PageRef#anchor], [PageRef#anchor text]
        nonlocal parent_id
        page_ref = m[1]
        anchor = m[2]
        link_text = m[3] if m.lastindex > 1 else None
        if debug_format: print(f'!bracket_anchored_link("{page_ref}", "{anchor}", "{link_text}")')
        url, link_text = page_ref_to_link_parts(page_ref, anchor, f'[{link_text}]', page_id, parent_id)
        return store_markdown_link(url, link_text)
    def transform_naked_interlink(m):
        # InterSite:path
        interlink = m[1]
        if debug_format: print(f'!naked_interlink("{interlink}")')
        interlink, extra = split_url_punct(interlink)
        link_text = interlink
        url = get_interlink_url(interlink)
        if url is None:
            return m[0]
        link_text = id
        return store_link_or_image(interlink, link_text) + extra
    def transform_naked_url(m):
        # url
        url = m[1]
        if debug_format: print(f'!naked_url("{url}")')
        url, extra = split_url_punct(url)
        return store_link_or_image(url) + extra
    def transform_anchored_link(m):
        # PageRef#anchor
        nonlocal parent_id
        page_ref = m[1]
        anchor = m[2]
        if debug_format: print(f'!anchored_link("{page_ref}","{anchor}")')
        url, link_text = page_ref_to_link_parts(page_ref, anchor, None, page_id, parent_id)
        return store_markdown_link(url, link_text)
    def transform_naked_link(m):
        # PageRef
        nonlocal parent_id
        page_ref = m[1]
        if debug_format: print(f'!naked_link("{page_ref}")')
        url, link_text = page_ref_to_link_parts(page_ref, None, None, page_id, parent_id)
        return store_markdown_link(url, link_text)



    # Raw HTML blocks
    if RawHtml:
        if not html_allowed:
            raise 'Raw HTML block encountered, not supported in output.'
        text = re.sub(r'<html>((.|\n)*?)</html>', transform_raw, text)

    # Quote HTML
    text = quote_html(text)

    # (Begin of first invocation of CommonMarkup.)

    # <nowiki> blocks
    def transform_nowiki(m):
        if debug_format: print(f'!nowiki')
        return store_raw(m[1])
    text = re.sub(r'&lt;nowiki&gt;((.|\n)*?)&lt;/nowiki&gt;', transform_nowiki, text)

    # <pre>, <code> blocks
    text = re.sub(r'&lt;(pre|code)&gt;((.|\n)*?)&lt;/\1&gt;', transform_pre, text)

    # Now translate allowed HTML tags back to unquoted HTML.
    if HtmlTags:
        text = re.sub(rf'&lt;({html_pairs_pattern})(\s.*?)?&gt;(.*?)&lt;/\1&gt;', r'<\1\2>\3</\1>', text, flags=re.I)
        text = re.sub(rf'&lt;({html_single_pattern})(\s.*?)?/?&gt;', r'<\1\2>', text, flags=re.I)
    else:
        # These markup tags are always supported:
        text = re.sub(rf'&lt;(b|i|strong|em)(\s.*?)?&gt;(.*?)&lt;/\1&gt;', r'<\1\2>\3</\1>', text, flags=re.I)

    # Not implemented here: <tt>

    # Line breaks.
    #
    # Standard Markdown uses two trailing spaces, which is nuts because they're
    # so easy to miss in an editor - and some editor configuration will
    # automatically remove them. Most processors accept HTML-style breaks, so
    # use those instead.
    text = re.sub(r'&lt;br\s*/?&gt;', r'<br>', text)

    if HtmlLinks:
        text = re.sub('&lt;A(\s.+?)&gt;(.*?)&lt;/A&gt;', transform_html_link, flags=re.I)
    
    # Free links [[page_name]], [[page_name | link_text]]
    if FreeLinks:
        text = re.sub(fr'\[\[{free_link_pattern}(?:\|([^]]+))?\]\]', transform_free_link, text)

    if BracketText:
        # Bracket links with text [url link-text], [interlink link-text]
        text = re.sub(rf'\[{url_pattern}\s+([^\]]+?)\]', transform_bracket_url, text)
        text = re.sub(rf'\[{inter_link_pattern}\s*([^\]]+?)\]', transform_bracket_interlink, text)
        if WikiLinks and BracketWiki:
            # Bracket links with text: [page text], [page#anchor text]
            text = re.sub(rf'\[{link_pattern}\s+([^\]]+?\]', transform_bracket_link, text)
            text = re.sub(rf'\[{anchored_link_pattern}\s+([^\]]+?\]', transform_bracket_anchored_link, text)

    # Bracket links, no text: [url], [interlink]
    text = re.sub(rf'\[{url_pattern}\]', transform_bracket_url, text)
    text = re.sub(rf'\[{inter_link_pattern}\]', transform_bracket_interlink, text)

    # Naked links
    text = re.sub(rf'\b{url_pattern}', transform_naked_url, text)
    text = re.sub(rf'\b{inter_link_pattern}', transform_naked_interlink, text)

    if WikiLinks:
        text = re.sub(rf'{anchored_link_pattern}', transform_anchored_link, text)
        text = re.sub(rf'{link_pattern}', transform_naked_link, text)

        # RFC pattern
        # ISBN pattern

    # Horizontal rules
    #
    # UseMod optionally supports several thicknesses. Markdown does not, so
    # we ignore that option.
    #
    # Markdown best practice is to ensure a blank line before and after.
    #
    # Surprisingly, UseMod does not require these markers to be at the
    # beginning of a line, or alone on a line, or anything like that.
    #
    # Given the latter two facts, we take a pretty ham-fisted approach.
    text = re.sub('----+', '\n\n---\n\n', text)

    # (End of first invocation of CommonMarkup.)

    # List start fix
    #
    # Markdown best practice requires a blank line before a list. Do this before
    # the adjacent lists fix, because we make an exception there.
    text = re.sub(r'^(?!\*)(.*\S.*)\n\*', r'\1\n\n*', text, flags=re.MULTILINE)

    # Adjacent lists fix
    #
    # UseMod allows a blank line to separate two similar lists. Markdown weirdly
    # interprets this as a single "loose" list, where every list item gets
    # wrapped as a paragraph, making the list spacing weird.
    #
    # For bullet lists, this can be fixed by causing a line break without an
    # empty line. The standard Markdown fix for this is two spaces at the end of
    # the last item to indicate a line break, but that's impossible to edit.
    # Most processors will accept HTML <br>, but you need two of them to
    # introduce the separator between lists. This is easier to do by adjusting
    # the wiki text before transforming to Markdown.
    #
    # For numbered lists, the problem cannot be fixed. There is no way to get
    # Markdown to restart numbering for the second list, it treats them as one.
    text = re.sub(r'^\*(.*?)\n\s*\n\*', r'*\1\n<br><br>\n*', text, flags=re.MULTILINE)
    if re.search(r'^\#[^\n]*(\n\s*)+\n\#', text, flags=re.MULTILINE):
        print(f'WARNING: Page contains adjacent numbered lists separated by blank lines which will misbehave in Markdown.')

    text = usemod_lines_to_markdown(text)

    # List depth error fix
    #
    # UseMod allows a list to start at a level higher than one. In Markdown,
    # the indentation used to indicate level gets misinterpreted.
    # Too hard to fix.

    # Markdown Emphasis
    #
    # UseMod's ''text'' => Markdown's *text* (italics)
    # UseMod's '''text''' => Markdown's **text** (bold)
    #
    # Make sure this is done after all lists are translated,
    # since the asterisks would be trouble otherwise.
    text = re.sub(r"<em>([^'\n]+?)</em>", r'*\1*', text)
    text = re.sub(r"<strong>([^'\n]+?)</strong>", r'**\1**', text)

    # <toc>
    #
    # You will need a Markdown processor or plugin that can translate this.
    text = re.sub('&lt;toc&gt;', '[[toc]]', text)

    if debug_format:
        print('!===============================')
        print(text)
        print('!===============================')
    return restore_chunks(text)

def usemod_lines_to_markdown(page_text):
    # UseMod had a function to do line-by-line processing of things that build
    # nested HTML contexts, like lists, tables, etc. Since we're translating to
    # Markdown, we are not generating nested output syntax. Therefore, we could
    # do some of these by operating on the whole page at once. However, the
    # order in which things are transformed matters sometimes, so we have kept
    # them here for now.

    page_markdown = ""
    heading_numbers = []
    table_mode = False
    numbered_list_mode = False
    list_item_count = 0

    for line in page_text.splitlines():
        if debug_format: print(f'in : {line}')
        line = line + '\n'

        # TODO: Definitions

        # Monospaced text
        #
        # UseMod checks this later, but we have to put it before
        # the list transformations because Markdown syntax adds
        # spaces at start of line.
        #
        # UseMod is triggered by a single space and preserves the rest.
        # Markdown requires four spaces (or a tab).
        line = re.sub(r'^([ \t].*)', r'    \1', line)

        # Indented text
        #
        # Markdown doesn't support indented text at all, but we convert that to
        # blockquotes.
        def transform_indented_text(m):
            depth = len(m[1])
            if debug_format: print(f' !indented_text(depth {depth})')
            prefix = '>'*depth
            return f'{prefix}'
        line = re.sub(r'^(:+)', transform_indented_text, line)

        # Unordered lists
        #
        # UseMod lists indicate sublists by number of asterisks, and you can
        # omit the space after them. Markdown wants you to indent sublists and
        # requires a space afterwards.
        def transform_unordered_list_item(m):
            depth = len(m[1])
            if debug_format: print(f' !unordered_list_item(depth {depth})')
            prefix = '  '*(depth-1)
            return f'{prefix}*'
        line = re.sub(r'^(\*+)', transform_unordered_list_item, line)

        # Ordered lists
        #
        # UseMod lists indicate sublists by number of hashes, and you can omit
        # the space after them. Markdown wants you to indent sublists and
        # requires a space afterwards.
        #
        # This must be done before headings, otherwise Markdown headings will
        # look like numbered list.
        def transform_ordered_list_item(m):
            nonlocal numbered_list_mode
            nonlocal list_item_count
            depth = len(m[1]);
            if debug_format: print(f' !ordered_list_item(depth {depth})')
            prefix = '  '*(depth-1)
            if numbered_list_mode:
                list_item_count = list_item_count + 1
            else:
                list_item_count = 1
            return f'{prefix}{list_item_count}.'
        line, match_count = re.subn(r'^(#+)', transform_ordered_list_item, line)
        numbered_list_mode = (match_count != 0)

        # Emphasis. Translate to HTML, later to Markup.
        line = re.sub("('*)'''(.*?)'''", r"\1<strong>\2</strong>", line)
        line = re.sub("''(.*?)''", r"<em>\1</em>", line)

        def transform_table_line(m):
            nonlocal table_mode
            fields = m[1][:-2].split('||')
            if debug_format: print(f'!table_line({len(fields)} fields)')
            result = f'|{"|".join(fields)}|'
            if not table_mode:
                header_separator = '|'.join('-'*len(x) for x in fields)
                # In many processors, Markdown tables *must* have a header line
                # to be recognized as such. Some processors will accept a header
                # line with header labels preceding it. As a compromise, if we
                # detect that every field of this first row has a bolding
                # marker, we'll assume that they are header labels.
                if all(map(lambda f : re.search("(<b>|<strong>)",f), fields)):
                    result = f'{result}\n|{header_separator}|'
                else:
                    result = f'\n|{header_separator}|\n{result}'
            return result
        line, match_count = re.subn(r'^\|\|((.*?\|\|)+)', transform_table_line, line)
        table_mode = match_count != 0

        # Headings
        #
        # UseMod is forgiving about the number of delim chars at the end, and it
        # allows body text after the end delimiter.
        #
        # UseMod allows monospaced heading - one or more spaces before the
        # heading marker. We don't try to translate that, but we'll allow and
        # ignore the leading spaces.
        if UseHeadings:
            def wiki_heading_number(number, depth):
                if number is None: return ''
                depth = depth -1
                if depth <= 0: return ''
                while len(heading_numbers) < depth-1:
                    heading_numbers.append(1)
                if len(heading_numbers) < depth:
                    heading_numbers.append(0)
                while len(heading_numbers) > depth:
                    heading_numbers.pop()
                heading_numbers[-1] = heading_numbers[-1] + 1
                number = '.'.join([str(n) for n in heading_numbers]) + '.'
                return f'{number} '
            def transform_heading(m):
                depth = min(len(m[1]), 6)
                number = m[2]
                text = m[3]
                rest = "\n" + m[4]
                number = '' if number is None else wiki_heading_number(number, depth)
                if debug_format: print(f'!heading({depth}, {number}, "{text}")')
                return f'{"#"*depth} {number}{text}\n{rest}'
            line = re.sub(r'^\s*(=+)\s+(#\s+)?(.*?)\s+=+(.*)$', transform_heading, line)

        if debug_format: print(f'out: {line}')
        page_markdown = page_markdown + line

    return page_markdown


def quote_html(txt):
    # Allow character quotes, otherwise translate ampersands.
    txt = re.sub('&(?![#a-zA-Z0-9]+;)','&amp;', txt)
    txt = re.sub(r'\<','&lt;', txt)
    txt = re.sub(r'\>','&gt;', txt)
    return txt;

def split_url_punct(url):
    # Remove delimiters if present
    url, n = re.subn(r'""$', '', url)
    if n > 0:
        return url, ''
    m = re.match(r'^(.*?)([^a-zA-Z0-9/\x80-\xff]+)?$', url)
    punct = '' if m.lastindex < 2 else m[2]
    return m[1], punct

def page_ref_to_link_parts(page_ref, anchor, link_text, page_id, parent_id):
    if link_text is None:
        if FreeLinks:
            link_text = page_ref.replace("_"," ")
        else:
            link_text = page_ref

    if FreeLinks:
        page_ref = free_to_normal(page_ref)
    if anchor is not None:
        page_ref = f'{page_ref}#{anchor}'
        link_text = f'{link_text}#{anchor}'

    # If the reference is to a sub-page with an implicit parent,
    # prepend the proper parent's id. That's either the current page's id,
    # or its parent's id if it's a sub-page.
    page_ref = re.sub('^/', f'{parent_id if parent_id else page_id}/', page_ref)

    # If the current page is a sub-page and we are generating relative links,
    # navigate up one step.
    if page_links_relative and parent_id:
        page_ref = f'../{page_ref}'

    # We generate links using a site-wide prefix and suffix.
    url = f'{page_link_prefix}{page_ref}{page_link_suffix}'
    return (url, link_text)

def get_interlink_url(interlink):
    t = interlink.split(':',1)
    if len(t) != 2:
        return None # Something odd going on, reject it.
    site, remote_page = t
    remote_page = remote_page.replace('&amp;','&')
    url = intermap.get(site)
    if url is not None:
        url = url + remote_page
    return url

def free_to_normal(title):
    # Capitalize letters after certain chars.
    # Had to dig into the Perl code to find the right approach for this!
    title = re.sub(' ','_',title)
    title = title[0:1].capitalize() + title[1:] 
    title = re.sub('__+', '_', title)
    title = re.sub('^_','', title)
    title = re.sub('_$', '', title)
    if (UseSubpage):
        title = re.sub('_/', '/', title)
        title = re.sub('/_', '/', title)
    if FreeUpper:
        title = re.sub(r'([-_.,\(\)/])([a-z])', lambda m: m[1] + m[2].capitalize(), title)
    return title

import argparse
import pathlib

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Convert UseMod wiki pages to Markdown.',
        epilog="""
            Converting a single file does not provide reliable conversion, and
            is mostly useful for debugging.""")
    parser.add_argument('input', type=pathlib.Path, help='UseMod data directory, or a single UseMod page file.')
    parser.add_argument('output_dir', type=pathlib.Path, help='Output directory, created if missing. Required with directory input, disallowed with single-file input.', nargs='?')
    parser.add_argument('--debug', help='Generate debug output.', action='store_true')
    parser.add_argument('--silent', help='Suppress progress messages.', action='store_true')
    parser.add_argument('--overwrite', help='Overwrite existing output file(s).', action='store_true')
    parser.add_argument('--page-link-suffix', help='Suffix for all page link URLs.', default=page_link_suffix)
    parser.add_argument('--page-link-prefix', help='Prefix for all page link URLs.', default=page_link_prefix)
    parser.add_argument('--page-links', help='Indicates if page links will be absolute or relative. If relative, implicit sibling links from sub-pages get an extra "../" prefix.', choices=['rel','abs'])
    parser.add_argument('--config-file', help='Overrides location of UseMod config file, or provides it for a single-file conversion.')
    args = parser.parse_args()

    input = args.input
    output_dir = args.output_dir
    overwrite_outputs = args.overwrite
    debug_format = args.debug
    supress_msgs = args.silent
    page_link_suffix = args.page_link_suffix
    page_link_prefix = args.page_link_prefix
    if not args.page_links:
        url_parts = urlparse(page_link_prefix)
        if (url_parts.path and url_parts.path.startswith("/")):
            page_links_relative = False
        else:
            page_links_relative = True
        if not supress_msgs: print(f'Inferred --page-links-relative={page_links_relative}') 
    elif args.page_links == "rel":
        page_links_relative = True
    elif args.page_links == "abs":
        page_links_relative = False

    init_link_patterns()

    input = input.resolve()

    if input.is_file():
        if not supress_msgs: print(f'Assuming input file {input} is a page file.')
        if output_dir:
            sys.exit('You may not specify an output when converting a single file.')
        if args.config_file:
            read_config(args.config_file)
        else:
            print('WARNING: No config file specified.')
        convert_page_file(input, None)
    else:
        if not input.is_dir():
            sys.exit('UseMod wiki db directory not found.')
        if not (input / 'page').exists():
            sys.exit('UseMod page directory not found.')
        if output_dir is not None:
            output_dir.mkdir(exist_ok=True)
        if args.config_file:
            read_config(args.config_file)
        else:
            read_config((input / "config").resolve())
        usemod_pages_to_markdown_files(input, output_dir)


