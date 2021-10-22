#!/usr/bin/env python

"""
Converts UseMod wiki pages to markdown files .

TODO: 
* Finish UseModish rewrite
* Tables
* Front matter, once I know what I want.
* Options should come from command line. (base URL, debugging)
* trailing slash on page URLs should be optional
* read UseMod config file?

"""

# Standard packages
import datetime
import io
import os
import re
import sys
from os.path import join

# Additional packages
import yaml

# options
debug_format = False
base_url='{{ wiki_base_path }}'
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

    initialize_intermap(input_dir)

    for letter_dir in (input_dir / 'page').resolve().iterdir():
        if letter_dir.is_dir():
            for page_item in letter_dir.iterdir():
                if page_item.is_file():
                    convert_page_file(page_item, output_dir)
                elif page_item.is_dir() & UseSubpage:
                    for subpage_item in page_item.iterdir():
                        subpage_output_dir = output_dir / page_item.name
                        subpage_output_dir.mkdir(parents=True, exist_ok=True)
                        convert_page_file(subpage_item, subpage_output_dir, page_item.name)

    # for root, _, files in os.walk(join(input_dir, 'page')):
    #     for file in files:
    #         convert_page_file(join(root, file), output_dir)

def initialize_intermap(input_dir):
    global intermap
    global intermap_prefix
    intermap = {}
    with open((input_dir / 'intermap').resolve()) as fh:
        for line in fh:
            key, url = line.strip().split(' ', 1)
            intermap[key] = url
    if not 'LocalWiki' in intermap:
        intermap['LocalWiki'] = base_url;
    if not 'Local' in intermap:
        intermap['Local'] = base_url;
    intermap_prefix = f'(P<intermap_key>{"|".join(intermap)}):'

def convert_page_file(file, output_dir, parent_id = None):
    print (f'Converting file {file}')
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
        write_post(sys.stdout, page_id, dt, markdown_text)
    else:
        output_file = f'{page_id}.md'
        filename = sys.stdout if output_dir is None else (output_dir / output_file).resolve()
        out_fh = io.open(filename, 'w', encoding='utf-8')
        write_post(out_fh, page_id, dt, markdown_text)

    #print(' timestamp:', timestamp, ' date:', dt.isoformat().replace('T', ' '), '\n')

def usemod_data_to_dictionary(buf, fs):
    s = buf.split(fs)
    keys = s[::2]
    vals = s[1::2]
    assert len(keys) == len(vals)
    return dict(list(zip(keys, vals)))

def write_post(out_fh, title, dt, txt):
    frontmatter = {'title': title,
                   'date': dt.isoformat()
                  }

    out_fh.write('---\n')
    yaml.dump(frontmatter, out_fh, default_flow_style=False)
    out_fh.write('---\n\n')

    out_fh.write(txt)
    out_fh.close()

# Pattern helpers

# Tags allowed if HtmlTags is true. Not particularly safe.
#
# Target Markdown may or may not support these.
#
# Tags which have Markdown equivalents have been removed.
htmlSingle = ['br', 'p', 'hr', 'li', 'dt', 'dd', 'tr', 'td', 'th']
htmlSingleExpr = re.compile(rf'&lt;({"|".join(htmlSingle)})(\s.*?)?/?&gt;')
htmlPairs = ['b', 'i', 'u', 'font', 'big', 'small', 'sub', 'sup', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'cite', 'code',
    'em', 's', 'strike', 'strong', 'tt', 'var', 'div', 'center', 'blockquote', 'ol', 'ul', 'dl', 'table', 'caption'] + htmlSingle
htmlPairExpr = re.compile(rf'&lt;({"|".join(htmlPairs)})(\s.*?)&gt;(.*?)&lt;/\1%gt;')

# Tags allowed always:
htmlTrivial = ['b', 'i', 'strong', 'em']
htmlTrivialExpr = re.compile(rf'&lt;({"|".join(htmlTrivial)})(\s.*?)&gt;(.*?)&lt;/\1%gt;')

# Set up link patterns, which can vary based on options.
def init_link_patterns():
    global freeLinkPattern
    global linkPattern
    global urlPattern
    global interLinkPattern
    global anchoredLinkPattern

    upperLetter = '[A-Z]'
    lowerLetter = '[a-z]'
    anyLetter = '[A-Za-z' + (']' if SimpleLinks else '_0-9]')
    # Main link pattern: lower between upper, then anything
    LpA = f'{upperLetter}+{lowerLetter}+{upperLetter}{anyLetter}*'
    # Optional subpage link pattern: upper, lower, then anything
    LpB = f'{upperLetter}+{lowerLetter}+{anyLetter}*'
    if UseSubpage:
        # Loose pattern: If subpage , it may be simple
        linkPattern = fr"((?:(?:{LpA})?\\/{LpB})|{LpA})"
    else:
        linkPattern = f'{LpA}'
    qDelim = '(?:"")?' # Optional quote delimiter - have never seen this used.
    anchoredLinkPattern = fr'{linkPattern}#(\w+){qDelim}'
    linkPattern = linkPattern + qDelim
    interSitePattern = f'{upperLetter}{anyLetter}+'
    interLinkPattern = fr'((?:{interSitePattern}:[^\]\s"<>{FS}]+){qDelim})'
    if FreeLinks:
        anyLetter = "[-,.()' _0-9A-Za-z]"
    if UseSubpage:
        freeLinkPattern = fr'((?:(?:{anyLetter}+)?/)?{anyLetter}+){qDelim}'
    else:
        freeLinkPattern = fr'({anyLetter}+){qDelim}'
    urlProtocols = 'https?|ftp|afs|news|nntp|mid|cid|mailto|wais|prospero|telnet|gopher'
    if NetworkFile:
        urlProtocols = urlProtocols + '|file'
    urlPattern = rf'((?:(?:{urlProtocols}):[^\]\s"<>{FS}]+){qDelim})'
    imageExtensions = '(gif|jpg|png|bmp|jpeg)'
    rfcPattern = r'RFC\s?(\d+)'
    isbnPattern = r'ISBN:?([0-9- xX]{`0,})'
    uploadPattern = rf'upload:([^\]\s"<>{FS}]+){qDelim}'


def usemod_page_to_markdown(page_text, page_id, parent_id):

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

    text = ''
    last_bracket_url_index = 0 # Counter for numbered reference links.
    indexed_bracket_urls = {}

    last_chunk_index = -1
    saved_markdown_chunks = []

    # Determine the id of the page to use as an implicit parent of subpages.
    # UseMod has a one-level hierarchy. If this page is a subpage, then 
    # pages referenced with a leading / are siblings, otherwise they are
    # subpages of this page.
    if parent_id is None:
        parent_id = page_id

    def make_marker(n):
        return f'{FS}{n}{FS}'

    def get_bracket_url_index(url):
        nonlocal last_bracket_url_index
        nonlocal indexed_bracket_urls
        i = indexed_bracket_urls.get(url)
        if i is None:
            last_bracket_url_index = last_bracket_url_index + 1
            indexed_bracket_urls[url] = last_bracket_url_index
            i = last_bracket_url_index
        return f'{i}'

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

    def store_pre(txt, tag):
        return store_raw(f'<{tag}>{txt}</{tag}>')
    def store_href(anchor, link_text=''):
        return f'<a{store_raw(anchor)}>{link_text}</a>'
    def store_page_link(page, link_text):
        if FreeLinks:
            # trim extra spaces
            page = page.strip()
            page = re.sub(r'\s*/\s*','/', page) # around subpage delim
        if link_text is not None: link_text = link_text.strip() 
        nonlocal parent_id
        return store_raw(get_page_link(page, None, link_text, parent_id))
    def store_bracket_url(url, link_text = None):
        if link_text is None:
            link_text = get_bracket_url_index(url)
        return store_raw(f'[{link_text}]({url})')
    def store_bracket_interlink(id, link_text = None):
        site, remotePage = id.split(':',1)
        remotePage = remotePage.replace('&amp;','&')
        url = intermap.get(site)
        if link_text is None:
            if url is None:
                return f'[{id}]'
            link_text = get_bracket_url_index(id)
        elif url is None:
            return f'[{id} {link_text}]'
        url = url + remotePage;
        link_text = f'[{link_text}]'
        return store_raw(f'[{link_text}]({url})')
    def store_bracket_link(page, link_text):
        return store_raw(get_page_link(page, None, f'[{link_text}]', parent_id))
    def store_bracket_anchored_link(page, anchor, link_text):
        return store_raw(get_page_link(page, anchor, f'[{link_text}]', parent_id))

    def transform_html_link(m):
        if debug_format: print('!html_link')
        return store_href(m.group(1), m.group(2))
    def transform_free_link(m):
        # We generate links using a site-wide prefix, and trailing slashes.
        page_name = m.group(1)
        link_text = m.group(2) if m.lastindex > 1 else None
        if debug_format: print (f'!free_link("{page_name}", "{link_text}")')
        return store_page_link(page_name, link_text)
    def transform_bracket_url(m):
        url = m.group(1)
        link_text = m.group(2) if m.lastindex > 1 else None
        if debug_format: print(f'!bracket_url("{url}", "{link_text}")')
        return store_bracket_url(url, link_text)
    def transform_bracket_interlink(m):
        id = m.group(1)
        link_text = m.group(2) if m.lastindex > 1 else None
        if debug_format: print(f'!bracket_interlink("{id}","{link_text}")')
        return store_bracket_interlink(id, link_text)
    def transform_bracket_link(m):
        id = m.group(1)
        link_text = m.group(2) if m.lastindex > 1 else None
        if debug_format: print(f'!bracket_link("{id}", "{link_text}")')
        store_bracket_link(id, link_text)
    def transform_bracket_anchored_link(m):
        id = m.group(1)
        anchor = m.group(2)
        link_text = m.group(3) if m.lastindex > 1 else None
        if debug_format: print(f'!bracket_anchored_link("{id}", "{anchor}", "{link_text}")')
        return store_bracket_anchored_link(id, anchor, link_text)
    def transform_naked_url(m):
        url = m.group(1)
        if debug_format: print(f'!naked_url("{url}")')
        return store_raw(f'<{url}>')
    def transform_naked_interlink(m):
        interlink = m.group(1)
        if debug_format: print(f'!naked_interlink("{interlink}")')
        return store_bracket_interlink(interlink)
    def transform_anchored_link(m):
        link = m.group(1)
        anchor = m.group(2)
        if debug_format: print(f'!anchored_link("{link}","{anchor}")')
        return store_raw(get_page_link(link, anchor, None, parent_id))
    def transform_link(m):
        link = m.group(1)
        if debug_format: print(f'!link("{link}")')
        return store_raw(get_page_link(link, None, None, parent_id))



    # Raw HTML blocks
    if RawHtml:
        if not html_allowed:
            raise 'Raw HTML block encountered, not supported in output.'
        def transform_raw(m):
            if debug_format: print(f'!raw')
            return store_raw(m.group(1))
        page_text = re.sub(r'<html>((.|\n)*?)</html>', transform_raw, page_text)

    # Quote HTML
    page_text = quote_html(page_text)

    # (Begin of first invocation of CommonMarkup.)

    # <nowiki> blocks
    def transform_nowiki(m):
        if debug_format: print(f'!nowiki')
        return store_raw(m.group(1))
    page_text = re.sub(r'&lt;nowiki&gt;((.|\n)*?)&lt;/nowiki&gt;', transform_nowiki, page_text)

    # <pre>, <code> blocks
    def transform_pre(m):
        tag = m.group(1)
        txt = m.group(2)
        if debug_format: print(f'!pre({tag})')
        return store_pre(txt,tag)
    page_text = re.sub(r'&lt;(pre|code)&gt;((.|\n)*?)&lt;/\1&gt;', transform_pre, page_text)

    # Now translate allowed HTML tags back to unquoted HTML.
    if HtmlTags:
        page_text = re.sub(htmlPairExpr, r'<\1\2>\3</\1>', page_text)
        page_text = re.sub(htmlSingleExpr, r'<\1\2>', page_text)
    else:
        page_text = re.sub(htmlTrivialExpr, r'<\1\2>', page_text)

    # Not implemented here: <tt>

    # Line breaks.
    #
    # Standard Markdown uses two trailing spaces, which is nuts.
    # Most processors accept HTML-style breaks.
    page_text = re.sub(r'&lt;br\s*/?&gt;', r'<br>', page_text)

    if HtmlLinks:
        page_text = re.sub('&lt;A(\s.+?)&gt;(.*?)&lt;/A&gt;', transform_html_link, flags=re.I)
    
    # Free links [[page_name]], [[page_name | link_text]]
    if FreeLinks:
        page_text = re.sub(fr'\[\[{freeLinkPattern}(?:\|([^]]+))?\]\]', transform_free_link, page_text)

    if BracketText:
        # Bracket links with text [url link-text], [interlink link-text]
        page_text = re.sub(rf'\[{urlPattern}\s+([^\]]+?)\]', transform_bracket_url, page_text)
        page_text = re.sub(rf'\[{interLinkPattern}\s*([^\]]+?)\]', transform_bracket_interlink, page_text)
        if WikiLinks and BracketWiki:
            # Bracket links with text: [page text], [page#anchor text]
            page_text = re.sub(rf'\[{linkPattern}\s+([^\]]+?\]', transform_bracket_link, page_text)
            page_text = re.sub(rf'\[{anchoredLinkPattern}\s+([^\]]+?\]', transform_bracket_anchored_link, page_text)

    # Bracket links, no text: [url], [interlink]
    page_text = re.sub(rf'\[{urlPattern}\]', transform_bracket_url, page_text)
    page_text = re.sub(rf'\[{interLinkPattern}\]', transform_bracket_interlink, page_text)

    # Naked links
    page_text = re.sub(rf'\b{urlPattern}', transform_naked_url, page_text)
    page_text = re.sub(rf'\b{interLinkPattern}', transform_naked_interlink, page_text)

    if WikiLinks:
        page_text = re.sub(rf'{anchoredLinkPattern}', transform_anchored_link, page_text)
        page_text = re.sub(rf'{linkPattern}', transform_link, page_text)

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
    page_text = re.sub('----+', '\n\n---\n\n', page_text)

    # (End of first invocation of CommonMarkup.)

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
    # introduce the separator between lists.
    #
    # For numbered lists, the problem cannot be fixed. There is no way to get
    # Markdown to restart numbering for the second list, it treats them as one.
    page_text = re.sub(r'^\*(.*?)\n\s*\n\*', r'*\1\n<br><br>\n*', page_text, flags=re.MULTILINE)
    if re.search(r'^\#[^\n]*(\n\s*)+\n\#', page_text, flags=re.MULTILINE):
        print(f'WARNING: Page contains adjacent numbered lists separated by blank lines which will misbehave in Markdown.')

    page_text = usemod_lines_to_markdown(page_text)


    # USEMODISH REWRITE CONTINUING HERE in CommonMarkup

    # Monospaced text
    #
    # UseMod is triggered by a single space and preserves the rest.
    # Markdown requires four spaces (or a tab).
    page_text = re.sub(r'^ (.*)$', r'    \1', page_text, flags=re.MULTILINE)

    # List start fix
    #
    # Markdown best practice requires a blank line before a list.
    page_text = re.sub(r'^(?!\*)(.*\S.*)\n\*', r'\1\n\n*', page_text, flags=re.MULTILINE)

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
    page_text = re.sub(r"<em>([^'\n]+?)</em>", r'*\1*', page_text)
    page_text = re.sub(r"<strong>;([^'\n]+?)</strong>", r'**\1**', page_text)

    # <toc>
    #
    # You will need a Markdown processor or plugin that can translate this.
    page_text = re.sub('&lt;toc&gt;', '[[toc]]', page_text)

    if debug_format:
        print('!===============================')
        print(page_text)
        print('!===============================')
    return restore_chunks(page_text)

#
# Handle some of the more complex things that 
# require tracking line-by-line context.
#
def usemod_lines_to_markdown(page_text):
    page_markdown = ""
    headingNumbers = []
    for line in page_text.splitlines():
        line = line + '\n'

        # TODO: Definitions
        # simple lists and indented text
        #
        # UseMod lists indicate sublists by number of asterisks, and you can
        # omit the space after them. Markdown wants you to indent sublists and
        # requires a space afterwards.
        #
        # Markdown doesn't support indented text at all, so we convert that to
        # a simple list.
        def transform_simple_list_item(m):
            if debug_format: print(f' !simple_list_item')
            prefix = '    '*(len(m.group(1))-1)
            return f'{prefix}* {m.group(2)}'
        line = re.sub(r'^([\*\:]+)\s*(.*)$', transform_simple_list_item, line)

        #
        # numbered lists
        #
        # UseMod lists indicate sublists by number of hashes, and you can omit
        # the space after them. Markdown wants you to indent sublists and
        # requires a space afterwards.
        #
        # This must be done before headings, otherwise Markdown headings will
        # look like numbered list.
        def transform_numbered_list_item(m):
            if debug_format: print(f' !numbered_list_item')
            prefix = '    '*(len(m.group(1))-1)
            return f'{prefix}1. {m.group(2)}'
        line = re.sub(r'^(#+)\s*(.*)$', transform_numbered_list_item, line)

        # TODO: Tables

        # (Begin second per-line invocation of CommonMarkup.)

        # Emphasis. Translate to HTML, later to Markup.
        line = re.sub("('*)'''(.*?)'''", "\1<strong>\2</strong>", line)
        line = re.sub("''(.*?)''", "<em>\1</em>", line)

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
                while len(headingNumbers) < depth-1:
                    headingNumbers.append(1)
                if len(headingNumbers) < depth:
                    headingNumbers.append(0)
                while len(headingNumbers) > depth:
                    headingNumbers.pop()
                headingNumbers[-1] = headingNumbers[-1] + 1
                number = '.'.join([str(n) for n in headingNumbers])
                return f'{number} '
            def transform_heading(m):
                depth = min(len(m.group(1)), 6)
                number = m.group(2)
                text = m.group(3)
                rest = "\n" + m.group(4)
                number = '' if number is None else wiki_heading_number(number, depth)
                if debug_format: print(f'!heading({depth}, {number}, "{text}")')
                return f'{"#"*depth} {number}{text}\n{rest}'
            line = re.sub(r'^\s*(=+)\s+(#\s+)?(.*?)\s+=+(.*)$', transform_heading, line)

        page_markdown = page_markdown + line

    return page_markdown


def quote_html(txt):
    # Allow character quotes, otherwise translate ampersands.
    txt = re.sub('&(?![#a-zA-Z0-9]+;)','&amp;', txt)
    txt = re.sub(r'\<','&lt;', txt)
    txt = re.sub(r'\>','&gt;', txt)
    return txt;

def get_page_link(id, anchor, link_text, parent_id):
    if link_text is None:
        link_text = id
        if FreeLinks:
            link_text = link_text.replace("_"," ")
    if FreeLinks:
        id = free_to_normal(id)
    id = re.sub('^/', f'{parent_id}/', id)
    if anchor is not None:
        id = f'{id}#{anchor}'
        link_text = f'{link_text}#{anchor}'
    return f'[{link_text}]({base_url}{id})'

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
        title = re.sub(r'([-_.,\(\)/])([a-z])', lambda m: m.group(1) + m.group(2).capitalize(), title)
    return title

def print_usage():
    print('Usage:')
    print('./usemod_to_markdown <usemod-data-dir> <output-dir>')
    print('./usemod_to_markdown <usemod-page-file> <output-dir>')
    print('The second form converts one file and prints debug information.')

import argparse
import pathlib

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert UseMod wiki pages to Markdown.')
    parser.add_argument('input', type=pathlib.Path, help='UseMod data directory, or a single UseMod page file.')
    parser.add_argument('output_dir', type=pathlib.Path, help='Output directory.', nargs='?')

    args = parser.parse_args()

    input = args.input
    output_dir = args.output_dir

    init_link_patterns()

    if input.is_file():
        print('Assuming input file is a page file.')
        debug_format = True
        convert_page_file(input, output_dir)
    else:
        if not input.is_dir():
            sys.exit('UseMod wiki db directory not found')

        output_dir.mkdir(exist_ok=True)

        if not (input / 'page').exists():
            sys.exit('UseMod page directory not found')

        usemod_pages_to_markdown_files(input, output_dir)


