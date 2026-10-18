import unittest
from app.modules.m20_general_cognitive_worker.code_review690 import parse_unified_diff, review, CodeReviewError

def path_of(plus_line):
    d = "--- a/x\n" + plus_line + "\n@@ -0,0 +1,1 @@\n+v = 1\n"
    return parse_unified_diff(d)[0]["path"]

class HeaderPaths(unittest.TestCase):
    def test_diff_u_timestamp_dropped(self):
        self.assertEqual(path_of("+++ b/app.py\t2026-10-15 10:00:01.000000000 +0530"), "app.py")
    def test_timestamp_header_still_detects_missing_tests(self):
        d = "--- a/app.py\t1\n+++ b/app.py\t2\n@@ -0,0 +1,1 @@\n+x = 1\n"
        self.assertIn("missing-tests", {f["rule"] for f in review(d, [], author="a")["findings"]})
    def test_git_space_in_name_trailing_tab(self):
        self.assertEqual(path_of("+++ b/my file.py\t"), "my file.py")
    def test_quoted_space(self):
        self.assertEqual(path_of('+++ "b/my file.py"'), "my file.py")
    def test_quoted_escapes_quote_backslash_tab_newline(self):
        self.assertEqual(path_of(r'+++ "b/q\"u\\o\tt\ne.py"'), 'q"u\\o\tt\ne.py')
    def test_octal_utf8(self):
        self.assertEqual(path_of(r'+++ "b/caf\303\251.py"'), "café.py")
    def test_octal_short_and_nul_forms(self):
        self.assertEqual(path_of(r'+++ "b/a\1b.py"'), "a\x01b.py")
    def test_quoted_with_timestamp(self):
        self.assertEqual(path_of('+++ "b/a b.py"\t2026-10-15 10:00:00'), "a b.py")
    def test_quoted_name_that_looks_like_dev_null_prefix_kept(self):
        self.assertEqual(path_of('+++ "b/dir/x.py"'), "dir/x.py")
    def test_malformed_quotes_refused(self):
        for bad in ('+++ "b/unterminated.py', '+++ "b/x.py"junk', r'+++ "b/bad\q.py"', r'+++ "b/big\777.py"', '+++ "b/end\\'):
            with self.subTest(bad=bad), self.assertRaises(CodeReviewError):
                path_of(bad)
    def test_invalid_utf8_refused_not_collapsed(self):
        for bad in (r'+++ "b/\377.py"', r'+++ "b/\376.py"', r'+++ "b/\303.py"', r'+++ "b/\200x.py"'):
            with self.subTest(bad=bad), self.assertRaises(CodeReviewError):
                path_of(bad)
    def test_distinct_valid_names_stay_distinct(self):
        self.assertNotEqual(path_of(r'+++ "b/caf\303\251.py"'), path_of(r'+++ "b/caf\303\250.py"'))
    def test_existing_unquoted_forms_unchanged(self):
        self.assertEqual(path_of("+++ b/dir/x.py"), "dir/x.py")
        self.assertEqual(path_of("+++ dir/x.py"), "dir/x.py")
        self.assertEqual(path_of("+++  odd.py"), "odd.py")
    def test_dev_null_unchanged(self):
        self.assertEqual(path_of("+++ /dev/null"), "/dev/null")
if __name__ == "__main__":
    unittest.main()
