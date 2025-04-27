#ifndef _CFILE_H
#define _CFILE_H
#include <stdio.h>

#include "more-c-stuff.h"

static const char* _CH_SYMBOL_VALUES;

#define MY_INT 18
#define MY_FLOAT 98.125f

struct UnusedWillNotCauseConflict {
    void* f;
    more_c_stuff_t* more_c_stuff;
};

struct Foobar {
    int a;
    float b;
};

static void print_foobar(struct Foobar foobar) {
    printf("Foobar(%d, %f)\n", foobar.a, foobar.b);
}

static void print_int(int i) {
    printf("print_int(%d)\n", i);
}

static void print_float(float f) {
    printf("print_float(%f)\n", f);
}

static void print_bool(int i) {
    printf("print_bool(%d)\n", i);
}

static void print_symbol(int value) {
    printf("%s\n", &_CH_SYMBOL_VALUES[value]);
}


/*
NOTES ON RTTI
=============
0-3 = 8, 16, 32, 64 bit signed integers
4-7 = 8, 16, 32, 64 bit unsigned integers
8-9 = 16, 32, 64 bit floating point
... Data types
... arrays
... pointers
-----

no data for pointers that point to non-pointer data types are actaully needed
to be stored. Instead, the index of the pointed-to rtti is calculated as
pointer_rtti_index - total_rtti_table_size.

Separate to this array is a ctor-array with information about type constructors.
*/

#endif