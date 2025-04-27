# cedar-py
Cedar language compiler implemented in python

To compile and run the example:

$ python3 cedar.py  main.ce  --cc gcc -I test
Compilation complete. C code written to main.c

$ gcc main.c  -I test

$ ./a.out 
<output>