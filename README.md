# UseMod to Markdown convertor

A script to convert the pages of a [UseMod
wiki](http://www.usemod.com/cgi-bin/wiki.pl?UseModWiki) database to a set of
[Markdown](https://en.wikipedia.org/wiki/Markdown) files. 

The approach is somewhat inspired by a Python script by
[rajbot](https://github.com/rajbot/usemod_to_jekyll), but written from scratch.


This script is useful only if you have access to the UseMod wiki's data
directory. The main use case for it is to convert a UseMod wiki to one of the
current crop of static site content managers (static SCM). You will almost
certainly need to tweak the script to adapt it both to your wiki's usage
patterns and your SCM's conventions.

No attempt is made to preserve historical edits. UseMod was designed to keep
only the most recent few edits of a page anyway.

## Using the script

This script was developed using Python 3.8.

You'll want to use Python's package manager, pip to install and manage packages
needed by this script. This is usually installed with Python. You should be
able to run it directly from the command line with the command ```pip```.

It's also best to use a Python virtual enviroment. You can read plenty about
that
[here](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/).

The short version for setting up an environment after cloning this repository,
using Bash:

```
pip install --user virtualenv
cd my-project
python3 -m venv .venv           # Create a local environment
source .venv/bin/activate       # Activate the local environment
pip install -r requirements.txt # Installs pkgs needed here, in your env.
```

Later, when you come back to this project, you just need to run the
```source``` command before running this script.

If you change the script and add or remove dependencies on packages, you'll want
to update the requirements.txt. Read more about that
[here](https://note.nkmk.me/en/python-pip-install-requirements/), but the short
recipe for updating it is:

```
pip freeze > requirements.txt
```

For further help using the script, run ```./usemod-to-markdown.py -h```.

## Notes on output

Tables are translated to Markdown-style tables. Your Markdown processor may need
a plugin to process these, as they are not part of the CommonMark spec.
