#!/usr/bin/env python

"""
Converts UseMod wiki pages to markdown files .

TODO: 
* Sub-pages
* Front matter, one I know what I want.
* '''text'''
* <nowiki>
* <pre> blocks?
* better cmd line syntax?

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

# Markers used to separate data in UseMod database files.
FS = "\xb3"
FS1 = FS + "1"
FS2 = FS + "2"
FS3 = FS + "3"

# Globals
intermap = {}
intermap_prefix = ''
debug_format = False

def usemod_pages_to_markdown_files(input_dir, output_dir):

    initialize_intermap(input_dir)

    for root, _, files in os.walk(join(input_dir, 'page')):
        for file in files:
            convert_page_file(join(root, file), output_dir)

def initialize_intermap(input_dir):
    global intermap
    global intermap_prefix
    intermap = {}
    with open(join(input_dir, 'intermap')) as fh:
        for line in fh:
            key, url = line.strip().split(' ', 1)
            intermap[key] = url
    intermap_prefix = f'(P<intermap_key>{"|".join(intermap)}):'

def convert_page_file(file, output_dir):
    print (f'processing page file {file}')
    contents = open(file).read()
    #print contents

    page = usemod_data_to_dictionary(contents, FS1)
    revision = int(page['revision'])

    output_file, title = usemod_filename_to_output_filename_and_title(file)

    section = usemod_data_to_dictionary(page['text_default'], FS2)

    timestamp = section['ts']
    dt = datetime.datetime.fromtimestamp(float(timestamp))

    data = usemod_data_to_dictionary(section['data'], FS3)
    text = data['text']

    category = get_category(file)

    write_post(output_dir, output_file, title, dt, category, text)

    print(' wrote revision', revision)
    print(' timestamp:', timestamp, ' date:', dt.isoformat().replace('T', ' '), '\n')

def usemod_data_to_dictionary(buf, fs):
    s = buf.split(fs)
    keys = s[::2]
    vals = s[1::2]
    assert len(keys) == len(vals)
    return dict(list(zip(keys, vals)))

def usemod_filename_to_output_filename_and_title(usemod_file):
    assert usemod_file.endswith('.kp') or usemod_file.endswith('.db')
    title = os.path.basename(usemod_file)[:-3]
    output_file = f'{title}.md'
    return output_file, title

def get_category(file):
    category = None
    m = re.search(r'/(?:page|keep)/[A-Z]/(.+)/'+os.path.basename(file), file)
    if m:
        category = m.group(1)
    return category

def write_post(output_dir, output_file, title, dt, category, txt):
    filename = join(output_dir, output_file)
    frontmatter = {'layout': 'post',
                   'title': title,
                   'date': dt.isoformat().replace('T', ' ')
                  }

    if category is not None:
        frontmatter['category'] = category

    f = io.open(filename, 'w', encoding='utf-8')

    f.write('---\n')
    yaml.dump(frontmatter, f, default_flow_style=False)
    f.write('---\n\n')

    f.write(usemod_to_markdown(txt))
    f.close()

def usemod_to_markdown(input_txt):

    # For UseMod constructs, see:
    # - http://www.usemod.com/cgi-bin/wiki.pl?TextFormattingExamples
    # - http://www.usemod.com/cgi-bin/wiki.pl?TextFormattingRules
    #
    # For Markdown constructs, see:
    # - https://www.markdownguide.org/
    #
    # Order of transformations is significant, otherwise some translated
    # formatting will erroneously trigger later transformations. This could be
    # alleviated by introducing a temporary marker for translated constructs.

    text = ''
    refnum = 0 # Counter for numbered reference links.

    for line in input_txt.splitlines():

        if debug_format:
            print (f'<{line}')

        # Monospaced text
        #
        # UseMod is triggered by a single space and preserved the rest.
        # Markdown requires four spaces (or a tab).
        line = re.sub(r'^ (.*)$', r'    \1', line)

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

        # Free links
        def transform_free_link(m):
            if debug_format: print(f' !free_link')
            desc = m.group(3)
            title = m.group(1)
            if desc is None: desc = title
            fname = title.replace(' ', '_')
            return f'[{desc}]({fname}.html)'
        line = re.sub(r'\[\[(.*?)(\s+\|\s+(.*?))?\]\]', transform_free_link, line)

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

        #HTML-style breaks (using two end spaces, not a backslash)
        # Other non-standard possibilities are <br> or backslash
        line = re.sub(r'(?i)\s*<br\s*/?>\s*$', r'  ', line)

        if debug_format:
            print (f'>{line}')
        text += line + '\n'

    #fix lists that don't have required blank line above

    text = re.sub(r'^(?!\*)(.*\S.*)\n\*', r'\1\n\n*', text, flags=re.MULTILINE)

    return text

def print_usage():
    print('Usage:')
    print('./usemod_to_markdown <usemod-data-dir> <output-dir>')
    print('./usemod_to_markdown <usemod-page-file> <output-dir>')
    print('The second form converts one file and prints debug information.')

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print_usage()
        sys.exit(1)
    input = sys.argv[1]
    output_dir = sys.argv[2]


    if not os.path.exists(input):
        sys.exit('UseMod wiki input not found')

    if not os.path.exists(output_dir):
        sys.exit('The output directory was not found')

    # if len(glob.glob(join(output_dir, '*'))) > 0:
    #     #print glob.glob(join(output_dir, '*'))
    #     sys.exit('output directory should be empty')

    if os.path.isfile(input):
        print('Assuming input file is a page file.')
        debug_format = True
        convert_page_file(input, output_dir)
    else:
        if not os.path.exists(join(input, 'page')):
            sys.exit('UseMod page directory not found')

        if not os.path.exists(join(input, 'keep')):
            sys.exit('UseMod keep directory not found')

        usemod_pages_to_markdown_files(input, output_dir)


