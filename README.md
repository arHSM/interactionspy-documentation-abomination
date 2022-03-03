# interactionspy-documentation-abomintaion

Uh since i.py is having a documentation update of sorts,
I suggested a better idea, which includes scraping/extarcting all the docstring out
of the lib to genrate the documentation (tedious ikr)

so [`./scrape.py`](./scrape.py) is my ~~abomination~~ creation to extract all docstrings from
- classes
- methods
- functions

## Note to James (fl0w)

JAMES I SWEAR IF YOU DISAPPROVE OF THIS IN THE END THEN I'LL PERSONALLY COME TO YOU AND DELTE THE I.PY ORG

![James](https://cdn.discordapp.com/stickers/876896783937187850.png)

## Back to serious stuff

A `SUMMARY.md` can be found in the root dir for usage with mdbook.

Steps to set-up:
1. Download the [`./scrape.py`](./scrape.py) file.
2. Clone the i.py repo
3. Place the `interactions` folder at the same place as the extraction script.
4. Run the script

Notes:
- If you want to ignore the entire file then add a `# doc: module ignore`
  **at the top of the file**
- If you want to ignore particular classes, methods or functions you can do something like this
  ```py
  # doc: ignore
  # ClassName,comma_without_space_to_separate,Class.method
  # doc: end ignore
  ```
- Have fun /s
