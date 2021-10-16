### UseMod to Markdown convertor

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
