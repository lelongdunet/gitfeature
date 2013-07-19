##############################################################
#
#  Makefile for latex figures compilation
#  By Adrien LELONG
#
##############################################################

DIA= $(wildcard *.dia)
TEX= $(wildcard *.tex)
EPS= $(wildcard *.eps)
PDF= $(TEX:.tex=.pdf) $(DIA:.dia=.pdf)
PDFEPS= $(EPS:.eps=.pdf)

all: $(PDF)

pst: $(PDF)

eps: $(PDFEPS)

%.pdf: %.tex
	./bin/buildpstricks $<

%.tmp.pdf: %.dia
	dia $< -e $@

%.pdf: %.tmp.pdf
	pdfcrop $< $@

.PHONY: clean mrproper

clean :
	rm -rf ${OBJ}
	rm -rf Makefile.deps

mrproper: clean
	rm -rf $(EXEC)



