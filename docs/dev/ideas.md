

### Publishing information / Front/back cover / spine elements?
So far, only "inside pages" being set. Is cover / publishing information out of scope? All possible in XeTeX, but not 'easy'. E.g.a sparate run making use of color / graphicx  XeLaTeX packages may make more sence.
There is some barcode-creating code available (one package uses secial fonts, but some years ago DG found another piece of code that uses vrules).

Someone was working on producing covers. It would be good to get them involved and merge efforts.


------------------

### \w word|glossary entry\w* and other |attributes.

USFM3.0 has added the | symbol to several character styles. The most useful one is \w,  (the lemma [default] attribute of a \w ... \w* could trigger the
inclusion of glossary entries, for example). But in any case, their presence should be parsed and not cause processing errors.


----------------
### Milestones
The syntax: \foo ...\* is taken in usfm to indicate a milestone, a non-printable indication of some kind of context type. 

Script marked with \qt-s |who="Jesus"\* .... \qt-e\* might be used to mark up scripts applying different colouration for alternate speakers, for instance.
One method of using these might be to apply hooks based on milestones.

Effectively another category-like mechanism

-----------------

### Categories
\esb \cat People \cat*  
\esb*
  Might be added to  sidebars, etc, and is expected to alter formatting of any/all elements in the study matter. These in some way give an attribute (see above) to 
blocks of extended study material.
\cat may  appear within footnotes too. There should be some (pseudo stylesheet?) method of applying styling to elements in a given category.

What sort of things could a \cat alter / impose?
* Font, fontsize, justification, baseline etc, potentially for all elements
* Background colour, default foreground colour
* Watermark / cutout image.


Consider lifting magic from context?

coloured breakable/ normal paragraphs, could extend parlocs file  to mark top left / bottom right of each column.
