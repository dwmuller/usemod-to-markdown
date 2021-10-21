#!/usr/bin/env python

"""
Converts UseMod wiki pages to markdown files .

TODO: 
* Continue UseModish rewrite
  * Somehow broke adjacent list fix?
  * Some of the following items will be fixed, presumably
* Tables
* Numbered headings (e.g. starting with == #)
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
RawHtml     = True  # allow <html> regions (default False)
HtmlTags    = True  # allow unsafe HTML tags (default False)
HtmlLinks   = False # allow raw HTML links
FreeLinks   = True  # Allow double-bracket page links
SimpleLinks = False # Allow only letters in page names

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
    markdown_text = usemod_to_markdown(text, page_id, parent_id)

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

#urlPattern = re.compile(rf'((?:(?:{urlProtocols}:[^\\]\\s"<>{FS}]+){qdelim}')

# Tags allowed if HtmlTags is true. Not particularly safe.
# Target Markdown may or may not support these. 
htmlSingle = ['br', 'p', 'hr', 'li', 'dt', 'dd', 'tr', 'td', 'th']
htmlSingleExpr = re.compile(rf'&lt;({"|".join(htmlSingle)})(\s.*?)?/?&gt;')
htmlPairs = ['b', 'i', 'u', 'font', 'big', 'small', 'sub', 'sup', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'cite', 'code',
    'em', 's', 'strike', 'strong', 'tt', 'var', 'div', 'center', 'blockquote', 'ol', 'ul', 'dl', 'table', 'caption'] + htmlSingle
htmlPairExpr = re.compile(rf'&lt;({"|".join(htmlPairs)})(\s.*?)&gt;(.*?)&lt;/\1%gt;')

# Tags allowed always:
htmlTrivial = ['b', 'i', 'strong', 'em']
htmlTrivialExpr = re.compile(rf'&lt;({"|".join(htmlTrivial)})(\s.*?)&gt;(.*?)&lt;/\1%gt;')

# Set up patterns that vary based on options.
def set_variable_patterns():
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

    anyLetter = "[-,.()' _0-9A-Za-z]"

    global freeLinkExpr
    if UseSubpage:
        freeLinkExpr = re.compile(fr'\[\[((?:(?:{anyLetter}+)?/)?{anyLetter}+)(?:|([^]]+))?\]\]{qDelim}')
    else:
        freeLinkExpr = re.compile(fr'\[\[({anyLetter}+)(?:|([^]]+))?\]\]{qDelim}')

def usemod_to_markdown(page_txt, page_id, parent_id):

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
    refnum = 0 # Counter for numbered reference links.
    chunk_index = 0
    saved_markdown_chunks = {}

    # Determine the id of the page to use as an implicit parent of subpages.
    # UseMod has a one-level hierarchy. If this page is a subpage, then 
    # pages referenced with a leading / are siblings, otherwise they are
    # subpages of this page.
    if parent_id is None:
        parent_id = page_id

    def store_raw(html):
        nonlocal chunk_index
        nonlocal saved_markdown_chunks
        marker = f'{FS}{chunk_index}{FS}'
        saved_markdown_chunks[marker] = html
        chunk_index = chunk_index + 1
        return marker

    def store_pre(txt, tag):
        return store_raw(f'<{tag}>{txt}</{tag}>')

    def store_href(anchor, txt=''):
        return f'<a{store_raw(anchor)}>{txt}</a>'

    def store_page_link(page, name):
        if FreeLinks:
            # trim extra spaces
            page = page.strip()
            page = re.sub(r'\s*/\s*','/', page) # around subpage delim
        if name is not None: name = name.strip() 
        nonlocal parent_id
        return store_raw(get_page_link(page, name, parent_id))

    def restore_chunks(txt):
        for key, value in saved_markdown_chunks.items():
            if debug_format: print (f'!restoring {key} => {value}')
            txt = re.sub(key, value, txt)
        return txt

    # Raw HTML blocks
    #
    # Save these, if supported, before quoting HTML.
    #
    if RawHtml:
        if not html_allowed:
            raise 'Raw HTML block encountered, not supported in output.'
        def transform_raw(m):
            if debug_format: print(f'!raw')
            return store_raw(m.group(1))
        page_txt = re.sub(r'<html>((.|\n)*?)</html>', transform_raw, page_txt)

    # Quote HTML
    #
    # We always do this, although we may undo it later.
    page_txt = quote_html(page_txt)

    # <nowiki> blocks
    def transform_nowiki(m):
        if debug_format: print(f'!nowiki')
        return store_raw(m.group(1))
    page_txt = re.sub(r'&lt;nowiki&gt;((.|\n)*?)&lt;/nowiki&gt;', transform_nowiki, page_txt)

    # <pre>, <code> blocks
    def transform_pre(m):
        tag = m.group(1)
        txt = m.group(2)
        if debug_format: print(f'!pre({tag})')
        return store_pre(txt,tag)
    page_txt = re.sub(r'&lt;(pre|code)&gt;((.|\n)*?)&lt;/\1&gt;', transform_pre, page_txt)

    # Now translate allowed HTML tags back to unquoted HTML.
    if HtmlTags:
        page_txt = re.sub(htmlPairExpr, r'<\1\2>\3</\1>', page_txt)
        page_txt = re.sub(htmlSingleExpr, r'<\1\2>', page_txt)
    else:
        page_txt = re.sub(htmlTrivialExpr, r'<\1\2>', page_txt)
        page_txt = re.sub(r'&lt;br\s*/?&gt;', r'<br>', page_txt)

    if HtmlLinks:
        def transform_html_link(m):
            if debug_format: print('!html_link')
            store_href(m.group(1), m.group(2))
        page_txt = re.sub('&lt;A(\s.+?)&gt;(.*?)&lt;/A&gt;', transform_html_link, flags=re.I)
    
    # Free links
    if FreeLinks:
        def transform_free_link(m):
            # We generate links using a site-wide prefix, and trailing slashes.
            page = m.group(1)
            name = m.group(2)
            if debug_format: print (f'!free_link({page}, {name})')
            return store_page_link(page, name)
        page_txt = re.sub(freeLinkExpr, transform_free_link, page_txt)

    # USEMODISH REWRITE CONTINUING HERE in CommonMarkup

    # Monospaced text
    #
    # UseMod is triggered by a single space and preserves the rest.
    # Markdown requires four spaces (or a tab).
    page_txt = re.sub(r'^ (.*)$', r'    \1', page_txt, flags=re.MULTILINE)

    # List start fix
    #
    # Markdown best practice requires a blank line before a list.
    page_txt = re.sub(r'^(?!\*)(.*\S.*)\n\*', r'\1\n\n*', page_txt, flags=re.MULTILINE)

    # List depth error fix
    #
    # UseMod allows a list to start at a level higher than one. In Markdown,
    # the indentation used to indicate level gets misinterpreted.
    # Too hard to fix.

    # Adjacent lists fix
    #
    # UseMod allows a blank line to separate two similar lists. Markdown weirdly
    # interprets this as a single "loose" list, where every list item gets
    # wrapped as a paragraph, making the list spacing weird.
    #
    # For bullet lists, this can be fixed by causing a line break without an
    # empty line. Standard Markdown to fix for this is two spaces at the end of
    # the last item to indicate a line break, but that's impossible to edit.
    # Most processors will accept HTML <br>, but you need two of them to
    # introduce the separator between lists.
    #
    # For numbered lists, the problem cannot be fixed. There is no way to get
    # Markdown to restart numbering for the second list, it treats them as one.
    page_txt = re.sub(r'^(\*[^\n]*)\n\s*\n\*', r'\1\n<br><br>\n*', page_txt)
    if re.search(r'^\#[^\n]*(\n\s*)+\n\#', page_txt):
        print(f'WARNING: Page contains adjacent numbered lists separated by blank lines which will misbehave in Markdown.')

    # Emphasis
    #
    # UseMod's ''text'' => Markdown's *text* (italics)
    # UseMod's '''text''' => Markdown's **text** (bold)
    #
    # Luckily, both forms compose.
    page_txt = re.sub(r"'''([^'\n]+?)'''", r'**\1**', page_txt)
    page_txt = re.sub(r"''([^'\n]+?)''", r'*\1*', page_txt)
    #
    # UseMod also supports HTML-style bolding and italicizing
    page_txt = re.sub(r"&lt;i&gt;([^'\n]+?)&lt;/i&gt;", r'*\1*', page_txt)
    page_txt = re.sub(r"&lt;b&gt;([^'\n]+?)&lt;/b&gt;", r'**\1**', page_txt)

    for line in page_txt.splitlines():

        if debug_format:
            print (f'in : {line}')

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

        # Headings
        #
        # UseMod is forgiving about the number of delim chars at the end, and it
        # allows body text after the end delimiter.
        #
        # UseMod allows monospaced heading - one or more spaces before the
        # heading marker. We don't try to translate that, but we'll allow and
        # ignore the leading spaces.
        def transform_heading(m):
            if debug_format: print(f' !heading')
            level = len(m.group(1))
            title = m.group(2)
            rest = "\n" + m.group(3)
            return f'{"#"*level} {title}{rest}'
        line = re.sub(r'^\s*(=+)\s+(.*?)\s+=+(.*)$', transform_heading, line)

        # Plain links
        line = re.sub(r'(?<!\[)\b(https?://\S+)', r'<\1>', line)

        # Plain mailto links
        line = re.sub(r'(?<!\[)\bmailto:(\S+)', r'<\1>', line)

        # Interwiki links
        def transform_interwiki_link(m):
            if debug_format: print(f' !interwiki_link')
            key = m.group("intermap_key")
            url = f'{intermap[key]}{m.group("path")}'
            return f'[{m.group()}]({url})'
        line = re.sub(f'(?<!\[)\b{intermap_prefix}(P<path>\S+)', transform_interwiki_link, line)

        # Named URL links
        def transform_named_link(m):
            if debug_format: print(f' !named_link')
            refkey = m.group(2)
            ref = intermap.get(refkey)
            url = m.group(1) if ref is None else f'{ref}{m.group(3)}'
            desc = m.group(5)
            if desc is None:
                nonlocal refnum 
                refnum = refnum + 1
                desc = f'[{refnum}]'
            # Note: UseMod has a corner case that we don't emulate: When the
            # link is followed by a single space, the link text is the link
            # followed by a space.
            return f'[{desc}]({url})'
        line = re.sub(r'(?<!\[)\[((\S*?):(\S*?))(\s+(.+?))\]', transform_named_link, line)

        #camelcase links
        # Not used in our wikis, and not possible to process as simply as this,
        # because it would also match the inside of internal links.
        #line = re.sub(r'(\s|^)([A-Z][a-z]+[A-Z]+[a-z].*?)(\s|$)', r'\1[\2](\2.html)\3', line)

        if debug_format:
            print (f'out: {line}')
        text += line + '\n'

    # <toc>
    #
    # You will need a Markdown processor or plugin that can translate this.
    text = re.sub('&lt;toc&gt;', '[[toc]]', text)

    return restore_chunks(text)

def quote_html(txt):
    # Allow character quotes, otherwise translate ampersands.
    txt = re.sub('&(?![#a-zA-Z0-9]+;)','&amp;', txt)
    txt = re.sub(r'\<','&lt;', txt)
    txt = re.sub(r'\>','&gt;', txt)
    return txt;

def get_page_anchored_link(id, anchor, name, parent_id):
    if name is None:
        name = id
        if FreeLinks:
            name = name.replace("_"," ")
    if FreeLinks:
        id = free_to_normal(id)
    id = re.sub('^/', f'{parent_id}/', id)
    if anchor is not None:
        id = f"{id}#{anchor}"
        name = f"{name}#{anchor}"
    return f'[{name}]({base_url}{id})'

def get_page_link(id, name, parent_id):
    return get_page_anchored_link(id, None, name, parent_id)

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

    set_variable_patterns()

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


