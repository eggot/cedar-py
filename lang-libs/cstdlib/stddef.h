/*
 * This file is part of the C89 Standard Library declarations.
 * These declarations are platform-independent and provide the standard 
 * function signatures, macros, and types as specified in the ANSI C 
 * (C89) standard.
 *
 * This file is part of the Crise toolchain.
 */

#ifndef CRISE_STDDEF_H
#define CRISE_STDDEF_H

/* stddef.h - Common type definitions */

typedef unsigned long /* implementation-defined */ ptrdiff_t;
typedef unsigned long /* implementation-defined */ size_t;
#define NULL ((void *)0)
#define offsetof(type, member)  /* implementation-defined */

#endif /* CRISE_STDDEF_H */
