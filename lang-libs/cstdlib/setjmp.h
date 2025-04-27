/*
 * This file is part of the C89 Standard Library declarations.
 * These declarations are platform-independent and provide the standard 
 * function signatures, macros, and types as specified in the ANSI C 
 * (C89) standard.
 *
 * This file is part of the Crise toolchain.
 */

#ifndef CRISE_SETJMP_H
#define CRISE_SETJMP_H

/* setjmp.h - Non-local jumps */

typedef struct {
    /* unspecified content */
} jmp_buf;

int setjmp(jmp_buf env);
void longjmp(jmp_buf env, int val);

#endif /* CRISE_SETJMP_H */
