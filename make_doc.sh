#sphinx-apidoc -f -o source . # required only once to generate the heap.rst and modules.rst files. the -f is to overwrite previous editions of the same filename, the -o is to specify the output destination of the created files (which is source). The last argument is where the files to be documented are.

make clean # remove metadata from build so that all new changes are reflected. else some old stuff still remains
# alternately use rm -r build

make doctest # test whether the examples actually work or not.

# build the html code for the documentation
make html

# open the documentation
open build/html/index.html
