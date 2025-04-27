/*
 * This file is part of the C89 Standard Library declarations.
 * These declarations are platform-independent and provide the standard 
 * function signatures, macros, and types as specified in the ANSI C 
 * (C89) standard.
 *
 * This file is part of the Crise toolchain.
 */

#ifndef CRISE_FLOAT_H
#define CRISE_FLOAT_H

/* float.h - Floating-point limits */

#define FLT_RADIX       2       /* Radix of exponent representation */
#define FLT_ROUNDS      1       /* Rounding mode for floating-point addition */
#define FLT_DIG         6       /* Decimal digits of precision */
#define FLT_EPSILON     1E-5    /* Smallest positive number such that 1.0 + FLT_EPSILON != 1.0 */
#define FLT_MANT_DIG    24      /* Number of base-FLT_RADIX digits in the mantissa */
#define FLT_MAX         3.4E+38 /* Maximum representable finite floating-point number */
#define FLT_MAX_EXP     128     /* Maximum integer such that FLT_RADIX raised to that power is less than FLT_MAX */
#define FLT_MIN         1.2E-38 /* Minimum normalized positive floating-point number */
#define FLT_MIN_EXP     (-125)  /* Minimum integer such that FLT_RADIX raised to that power is greater than FLT_MIN */

/* Similar macros exist for double and long double types */

#endif /* CRISE_FLOAT_H */
