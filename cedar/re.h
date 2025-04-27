#include <assert.h>
#include <string.h>
#include <stdio.h>
#include <stddef.h>

#define _RE_ANCHOR_START 1
#define _RE_ANCHOR_END 2
#define _RE_ANCHOR_WORD 3
#define _RE_CHARCLASS 4
#define _RE_CHARCLASS_INV 5
#define _RE_QUANTIFIER 6
#define _RE_ALTERNATION 7
#define _RE_SEQUENCE 8
#define _RE_DOT 9
#define _RE_POSITIVE_LOOKAHEAD 10
#define _RE_CAPTURING_GROUP 11

struct Capture {
    const char* begin;
    const char* end;
};

struct MatchResult {
    size_t pc;
    size_t sp;
    int matched;
    int groups; // bitmask of assigned groups
};

int bc_is_word_char(char s) {
    return ('a' <= s && s <= 'z') || ('A' <= s && s <= 'Z') || ('0' <= s && s <= '9') || s == '_';
}

struct MatchResult _bc_match(const char* bytecode, size_t bytecode_len, const char* string, size_t string_len, size_t pc, size_t sp, struct Capture* captures, size_t captures_count);

int bc_match(const char* bytecode, size_t bytecode_len, const char* string, size_t string_len, struct Capture* captures, size_t captures_count) {
    struct MatchResult final_s = _bc_match(bytecode, bytecode_len, string, string_len, 0, 0, captures, captures_count);
    return final_s.matched;
}

struct MatchResult _bc_match(const char* bytecode, size_t bytecode_len, const char* string, size_t string_len, size_t pc, size_t sp, struct Capture* captures, size_t captures_count) {
    if (pc >= bytecode_len) return (struct MatchResult){pc, sp, /*false*/0, 0};

    unsigned char instr = bytecode[pc];
    switch (instr) {
        case _RE_SEQUENCE: {
            if (pc + 1 >= bytecode_len) return (struct MatchResult){pc, sp, /*false*/0, 0};
            size_t end = bytecode[pc + 1] + pc + 1;
            pc += 2;
            int groups = 0;
            while (pc < end && pc < bytecode_len) {
                struct MatchResult s = _bc_match(bytecode, bytecode_len, string, string_len, pc, sp, captures, captures_count);
                pc = s.pc;
                sp = s.sp;
                if (!s.matched) {
                    return (struct MatchResult){end, sp, /*false*/0, 0};
                }
                groups |= s.groups;
            }
            return (struct MatchResult){end, sp, /*true*/1, groups};
        }
        case _RE_CHARCLASS:
        case _RE_CHARCLASS_INV: {
            if (pc + 1 >= bytecode_len) return (struct MatchResult){pc, sp, /*false*/0, 0};
            size_t end = bytecode[pc + 1] + pc + 1;
            if (sp >= string_len) return (struct MatchResult){end, sp, /*false*/0, 0};
            pc += 2;
            int val = (unsigned char)string[sp];
            int matched = /*false*/0;
            struct MatchResult early_exit = {end, sp + 1, /*true*/1, 0};
            struct MatchResult regular_exit = {end, sp, /*false*/0, 0};
            if (instr == _RE_CHARCLASS_INV) {
                struct MatchResult temp = early_exit;
                early_exit = regular_exit;
                regular_exit = temp;
            }
            while (pc < end && pc + 1 < bytecode_len) {
                int lower = (unsigned char)bytecode[pc];
                int upper = (unsigned char)bytecode[pc + 1];
                pc += 2;
                if (lower <= val && val <= upper) {
                    return early_exit;
                }
            }
            return regular_exit;
        }
        case _RE_QUANTIFIER: {
            if (pc + 2 >= bytecode_len) return (struct MatchResult){pc, sp, /*false*/0, 0};
            unsigned char mn = bytecode[pc + 1];
            unsigned char mx = bytecode[pc + 2];
            int count = 0;
            pc += 3;
            int end_pc = -1;
            int groups = 0;
            while (count < mn) {
                struct MatchResult s = _bc_match(bytecode, bytecode_len, string, string_len, pc, sp, captures, captures_count);
                end_pc = s.pc; // We would only need to do this once, but it should be the same on every iteration anyway
                if (!s.matched) return (struct MatchResult){s.pc, sp, /*false*/0, 0};
                sp = s.sp;
                count++;
                groups |= s.groups;
            }
            while (mx == 255 || count < mx) {
                struct MatchResult s = _bc_match(bytecode, bytecode_len, string, string_len, pc, sp, captures, captures_count);
                if (!s.matched) break;
                sp = s.sp;
                count++;
                groups |= s.groups;
            }
            assert(end_pc >= 0);
            return (struct MatchResult){end_pc, sp, /*true*/1, groups};
        }
        case _RE_ALTERNATION: {
            struct MatchResult left_s = _bc_match(bytecode, bytecode_len, string, string_len, pc + 1, sp, captures, captures_count);
            if (left_s.matched) {
                pc = bytecode[left_s.pc] + left_s.pc; // Skip RHS
                return (struct MatchResult){pc, left_s.sp, /*true*/1, left_s.groups};
            }
            return _bc_match(bytecode, bytecode_len, string, string_len, left_s.pc + 1, sp, captures, captures_count);
        }
        case _RE_ANCHOR_START:
            return (struct MatchResult){pc + 1, sp, sp == 0, 0};
        case _RE_ANCHOR_END:
            return (struct MatchResult){pc + 1, sp, sp == string_len, 0};
        case _RE_ANCHOR_WORD: {
            int result = (sp == 0) || (sp == string_len) || (bc_is_word_char(string[sp - 1]) ^ bc_is_word_char(string[sp]));
            return (struct MatchResult){pc + 1, sp, result, 0};
        }
        case _RE_DOT:
            return (sp < string_len) ? (struct MatchResult){pc + 1, sp + 1, /*true*/1, 0} : (struct MatchResult){pc + 1, sp, /*false*/0, 0};
        case _RE_POSITIVE_LOOKAHEAD: {
            struct MatchResult result = _bc_match(bytecode, bytecode_len, string, string_len, pc + 1, sp, captures, captures_count);
            return (struct MatchResult){result.pc, sp, result.matched, result.groups};
        }
        case _RE_CAPTURING_GROUP: {
            if (pc + 1 >= bytecode_len) return (struct MatchResult){pc, sp, /*false*/0, 0};
            unsigned char group_number = bytecode[pc + 1];
            struct MatchResult result = _bc_match(bytecode, bytecode_len, string, string_len, pc + 2, sp, captures, captures_count);
            int g = 0;
            if (result.matched && group_number < captures_count) {
                captures[group_number].begin = &string[sp];
                captures[group_number].end = &string[result.sp];
                g = (1 << group_number);
            }
            return (struct MatchResult){result.pc, result.sp, result.matched, result.groups | g};
        }
        default: {
            // Everything else is a literal character
            int m = sp < string_len && string[sp] == (char)instr;
            return (struct MatchResult){pc + 1, sp + 1, m, 0};
        }
    }
}