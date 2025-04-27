/*
 * This file is part of the C89 Standard Library declarations.
 * These declarations are platform-independent and provide the standard 
 * function signatures, macros, and types as specified in the ANSI C 
 * (C89) standard.
 *
 * This file is part of the Crise toolchain.
 */

#ifndef CRISE_STDARG_H
#define CRISE_STDARG_H

/* stdarg.h - Variable argument handling */

typedef struct { /* implementation-defined */ } va_list;

void va_start(va_list ap, last);
void va_end(va_list ap);
type va_arg(va_list ap, type);

#endif /* CRISE_STDARG_H */
