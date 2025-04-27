/*
 * This file is part of the C89 Standard Library declarations.
 * These declarations are platform-independent and provide the standard 
 * function signatures, macros, and types as specified in the ANSI C 
 * (C89) standard.
 *
 * This file is part of the Crise toolchain.
 */

#ifndef CRISE_ERRNO_H
#define CRISE_ERRNO_H

/* errno.h - Error handling */

extern int errno;

#define EDOM        1  /* Domain error in mathematical functions */
#define ERANGE      2  /* Range error in mathematical functions */

#endif /* CRISE_ERRNO_H */
