/*
 * This file is part of the C89 Standard Library declarations.
 * These declarations are platform-independent and provide the standard 
 * function signatures, macros, and types as specified in the ANSI C 
 * (C89) standard.
 *
 * This file is part of the Crise toolchain.
 */

#ifndef CRISE_STDLIB_H
#define CRISE_STDLIB_H

#include <stddef.h>

/* stdlib.h - General utilities */

typedef struct {
    int quot;
    int rem;
} div_t;

typedef struct {
    long quot;
    long rem;
} ldiv_t;

#define EXIT_FAILURE    1   /* Unsuccessful termination */
#define EXIT_SUCCESS    0   /* Successful termination */
#define RAND_MAX        32767 /* Maximum value returned by rand() */
#define MB_CUR_MAX      1   /* Max number of bytes in multibyte character (in C89) */

void abort(void);
int abs(int n);
int atexit(void (*func)(void));
double atof(const char *str);
int atoi(const char *str);
long atol(const char *str);
void *calloc(size_t nmemb, size_t size);
div_t div(int numer, int denom);
void free(void *ptr);
char *getenv(const char *name);
long labs(long n);
ldiv_t ldiv(long numer, long denom);
void *malloc(size_t size);
int rand(void);
void *realloc(void *ptr, size_t size);
void srand(unsigned int seed);
void exit(int status);

void *bsearch(const void *key, const void *base, size_t nmemb, size_t size, 
              int (*compar)(const void *, const void *));
void qsort(void *base, size_t nmemb, size_t size, 
           int (*compar)(const void *, const void *));

int mblen(const char *str, size_t n);
size_t mbstowcs(wchar_t *dest, const char *src, size_t n);
int mbtowc(wchar_t *pwc, const char *str, size_t n);
size_t wcstombs(char *dest, const wchar_t *src, size_t n);
int wctomb(char *str, wchar_t wc);

#endif /* CRISE_STDLIB_H */
