/*
 * This file is part of the C89 Standard Library declarations.
 * These declarations are platform-independent and provide the standard 
 * function signatures, macros, and types as specified in the ANSI C 
 * (C89) standard.
 *
 * This file is part of the Crise toolchain.
 */

#ifndef CRISE_SIGNAL_H
#define CRISE_SIGNAL_H

/* signal.h - Signal handling */

typedef int sig_atomic_t;
typedef void (*sighandler_t)(int);

#define SIG_DFL  ((sighandler_t)0) /* Default signal handling */
#define SIG_ERR  ((sighandler_t)-1) /* Error return from signal */
#define SIG_IGN  ((sighandler_t)1) /* Ignore signal */

#define SIGABRT  6  /* Abort signal */
#define SIGFPE   8  /* Floating-point exception signal */
#define SIGILL   4  /* Illegal instruction signal */
#define SIGINT   2  /* Interrupt signal */
#define SIGSEGV  11 /* Segmentation violation signal */
#define SIGTERM  15 /* Termination request signal */

sighandler_t signal(int signum, sighandler_t handler);
int raise(int sig);

#endif /* CRISE_SIGNAL_H */
