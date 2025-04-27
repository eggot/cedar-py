/*
 * This file is part of the C89 Standard Library declarations.
 * These declarations are platform-independent and provide the standard 
 * function signatures, macros, and types as specified in the ANSI C 
 * (C89) standard.
 *
 * This file is part of the Crise toolchain.
 */

#ifndef CRISE_STDIO_H
#define CRISE_STDIO_H

/* stdio.h - Input/Output operations */

typedef struct { /* implementation-defined */ } FILE;
typedef struct { /* implementation-defined */ } fpos_t;

#define EOF        (-1)       /* End-of-file indicator */
#define FOPEN_MAX  20         /* Maximum number of files open simultaneously */
#define FILENAME_MAX 255      /* Maximum length of a file name */
#define BUFSIZ     512        /* Size of buffer used by setbuf */
#define _IOFBF     0          /* Full buffering */
#define _IOLBF     1          /* Line buffering */
#define _IONBF     2          /* No buffering */
#define SEEK_SET   0          /* Seek from beginning of file */
#define SEEK_CUR   1          /* Seek from current position in file */
#define SEEK_END   2          /* Seek from end of file */
#define TMP_MAX    238328     /* Maximum number of unique temporary file names */

FILE *fopen(const char *filename, const char *mode);
FILE *freopen(const char *filename, const char *mode, FILE *stream);
int fflush(FILE *stream);
int fclose(FILE *stream);

int remove(const char *filename);
int rename(const char *oldname, const char *newname);
FILE *tmpfile(void);
char *tmpnam(char *str);

int setvbuf(FILE *stream, char *buffer, int mode, size_t size);
void setbuf(FILE *stream, char *buffer);

int fprintf(FILE *stream, const char *format, ...);
int fscanf(FILE *stream, const char *format, ...);
int printf(const char *format, ...);
int scanf(const char *format, ...);
int sprintf(char *str, const char *format, ...);
int sscanf(const char *str, const char *format, ...);
int vfprintf(FILE *stream, const char *format, va_list arg);
int vprintf(const char *format, va_list arg);
int vsprintf(char *str, const char *format, va_list arg);

int fgetc(FILE *stream);
char *fgets(char *str, int n, FILE *stream);
int fputc(int c, FILE *stream);
int fputs(const char *str, FILE *stream);
int getc(FILE *stream);
int getchar(void);
char *gets(char *str); /* Note: gets is considered unsafe and was removed in C11 */
int putc(int c, FILE *stream);
int putchar(int c);
int puts(const char *str);
int ungetc(int c, FILE *stream);

size_t fread(void *ptr, size_t size, size_t nmemb, FILE *stream);
size_t fwrite(const void *ptr, size_t size, size_t nmemb, FILE *stream);

int fseek(FILE *stream, long int offset, int whence);
long int ftell(FILE *stream);
void rewind(FILE *stream);
int fgetpos(FILE *stream, fpos_t *pos);
int fsetpos(FILE *stream, const fpos_t *pos);

void perror(const char *str);

#endif /* CRISE_STDIO_H */
