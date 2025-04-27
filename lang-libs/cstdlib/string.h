/*
 * This file is part of the C89 Standard Library declarations.
 * These declarations are platform-independent and provide the standard 
 * function signatures, macros, and types as specified in the ANSI C 
 * (C89) standard.
 *
 * This file is part of the Crise toolchain.
 */

#ifndef CRISE_STRING_H
#define CRISE_STRING_H
#include <stddef.h>

/* string.h - String handling */

void *memcpy(void *dest, const void *src, size_t n);
void *memmove(void *dest, const void *src, size_t n);
char *strcpy(char *dest, const char *src);
char *strncpy(char *dest, const char *src, size_t n);
char *strcat(char *dest, const char *src);
char *strncat(char *dest, const char *src, size_t n);
int memcmp(const void *str1, const void *str2, size_t n);
int strcmp(const char *str1, const char *str2);
int strncmp(const char *str1, const char *str2, size_t n);
void *memchr(const void *str, int c, size_t n);
char *strchr(const char *str, int c);
size_t strcspn(const char *str1, const char *str2);
char *strpbrk(const char *str1, const char *str2);
char *strrchr(const char *str, int c);
size_t strspn(const char *str1, const char *str2);
char *strstr(const char *haystack, const char *needle);
char *strtok(char *str, const char *delim);
void *memset(void *str, int c, size_t n);
char *strerror(int errnum);
size_t strlen(const char *str);

#endif /* CRISE_STRING_H */
