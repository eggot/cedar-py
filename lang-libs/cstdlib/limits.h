/*
 * This file is part of the C89 Standard Library declarations.
 * These declarations are platform-independent and provide the standard 
 * function signatures, macros, and types as specified in the ANSI C 
 * (C89) standard.
 *
 * This file is part of the Crise toolchain.
 */

#ifndef CRISE_LIMITS_H
#define CRISE_LIMITS_H

/* limits.h - Sizes of integral types */

/*
 * NOTE: These are example values for type-inference to work in teh Crise compiler
 */

#define CHAR_BIT    8       /* Number of bits in a char */
#define CHAR_MAX    127     /* Maximum value of char */
#define CHAR_MIN    (-128)  /* Minimum value of char */
#define INT_MAX     2147483647  /* Maximum value of int */
#define INT_MIN     (-2147483648) /* Minimum value of int */
#define LONG_MAX    2147483647L   /* Maximum value of long */
#define LONG_MIN    (-2147483648L) /* Minimum value of long */
#define SCHAR_MAX   127     /* Maximum value of signed char */
#define SCHAR_MIN   (-128)  /* Minimum value of signed char */
#define SHRT_MAX    32767   /* Maximum value of short */
#define SHRT_MIN    (-32768) /* Minimum value of short */
#define UCHAR_MAX   255     /* Maximum value of unsigned char */
#define UINT_MAX    4294967295U /* Maximum value of unsigned int */
#define ULONG_MAX   4294967295UL /* Maximum value of unsigned long */
#define USHRT_MAX   65535   /* Maximum value of unsigned short */

#endif /* CRISE_LIMITS_H */
