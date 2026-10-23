"""
Parser for the grade sheets sent by the UFAZ education office.

Turns a "dirty" grade sheet (.xlsx / .csv) into a clean table of one
assignment: student ID -> grade.

Pipeline
--------
    read_sheet            read the file as is (header=None)
        |
    clean_table           (runs the four steps below in this order)
        |-- keep_student_rows   keep only rows whose ID starts with "224":
        |                       drops the faculty name, "Academic Year",
        |                       column titles, coefficients, empty rows and
        |                       the group average at the bottom
        |-- mark_missing        gaps ("abs", "ab", "na", "-", " ") -> NaN
        |-- fix_numbers         numbers written as text ("17, 5") -> 17.5;
        |                       the ID column is not touched
        |-- validate_table      unique IDs; every grade is a number 0-20 or
        |                       NaN; raises ValueError listing all problems
        |
    to_assignment_table   pick the grade column -> table "student_id | grade"

    parse_assignment      runs the whole pipeline in one call

Order matters: gaps become NaN before numbers are fixed, otherwise "abs"
would be left as text.

Functions
---------
read_sheet(path, sheet=None)
    Read one sheet without a header. `sheet` may be omitted if the file has
    only one sheet; ignored for .csv.

find_id_column(table, prefix="224")
    Return the column where values starting with `prefix` occur most often.

normalize_id(value)
    One cell -> clean ID string: 22423021.0 -> "22423021"; empty -> None.

keep_student_rows(table, prefix="224")
    Keep only student rows. Original row numbers (index) are kept, so
    row = index + 1 is the row number in Excel.

is_missing(value) / mark_missing(table)
    Detect a gap in one cell / replace all gaps in a table with NaN.

to_number(value) / fix_numbers(table, prefix="224")
    Convert a number written as text into float in one cell / in all
    columns except the ID column. Names and e-mails are left as is.

validate_table(table, prefix="224")
    Return a list of problems (empty list = table is fine).

clean_table(table, prefix="224", check=True)
    keep_student_rows -> mark_missing -> fix_numbers -> validate_table.
    check=False skips the validation.

to_assignment_table(table, grade_column, prefix="224")
    Cleaned table -> one assignment: index "student_id" (string),
    column "grade" (float, NaN for missing). `grade_column` is the column
    position in the original sheet, 0-based (A=0, B=1, C=2, ...).

parse_assignment(path, grade_column, sheet=None, prefix="224")
    read_sheet -> clean_table -> to_assignment_table.

Conventions
-----------
* Student IDs are strings, so tables from different sheets match.
* Grades are floats; a missing grade is NaN (what to do with it is decided
  later, when averages are computed).
* Each assignment is a separate table named like CS24L1S1MathMidterm
  (FACULTY + SEMESTER + SUBJECT + ASSIGNMENT). Tables can be combined
  without merge, aligned by student ID:
      wide = pd.concat({name: t["grade"] for name, t in tables.items()}, axis=1)
* All functions return new tables; the input table is never changed.

Example
-------
    from parser import parse_assignment

    math_midterm = parse_assignment(
        "grades/L1 math Midterm Grade Sheet.xlsx", grade_column=3, sheet="CS"
    )
"""

from pathlib import Path

import numpy as np
import pandas as pd

# How grade sheets mark a missing grade (compared lowercase, without spaces).
MISSING_TOKENS = {"abs", "ab", "absent", "na", "n/a", "nan", "-", ""}


def normalize_id(value):
    """Turn a cell into a clean ID string: 22423021.0 -> '22423021'.

    Returns None for empty cells.
    """
    if pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def find_id_column(table: pd.DataFrame, prefix: str = "224"):
    """Return the column where values starting with `prefix` occur most often.

    `table` should be read without a header (header=None), so that the
    title rows of the grade sheet do not become column names.
    """
    counts = {}
    for column in table.columns:
        ids = table[column].map(normalize_id)
        counts[column] = ids.str.startswith(prefix, na=False).sum()

    best = max(counts, key=counts.get)
    if counts[best] == 0:
        raise ValueError(f"No column with values starting with '{prefix}'")
    return best


def keep_student_rows(table: pd.DataFrame, prefix: str = "224") -> pd.DataFrame:
    """Drop every row that is not a student row.

    A student row is a row whose ID (in the column found by find_id_column)
    starts with `prefix`. This removes the faculty name, "Academic Year",
    "Semester 1", the column titles, coefficient rows, empty rows and the
    group average at the bottom -- none of them has an ID.

    The original row numbers (index) are kept, so later you can still say
    "row 9 of the Excel file".
    """
    id_column = find_id_column(table, prefix)
    ids = table[id_column].map(normalize_id)
    is_student = ids.str.startswith(prefix, na=False)
    return table[is_student].copy()


def is_missing(value) -> bool:
    """True if a cell is a gap: empty, only spaces, or a token like "abs"."""
    if pd.isna(value):
        return True
    if isinstance(value, str):
        return value.strip().casefold() in MISSING_TOKENS
    return False


def mark_missing(table: pd.DataFrame) -> pd.DataFrame:
    """Replace every gap ("abs", "ab", "na", "-", " ", empty) with np.nan.

    Real values -- numbers, names, e-mails -- are left untouched.
    Returns a new table; the original one is not changed.
    """
    return table.map(lambda value: np.nan if is_missing(value) else value)


def to_number(value):
    """Turn one cell into a float if it is a number written as text.

    "17, 5" -> 17.5,  "17,5" -> 17.5,  " 18 " -> 18.0,  12 -> 12.0
    Anything that is not a number (NaN, names, e-mails) is returned as is.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.replace(" ", "").replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return value
    return value


def fix_numbers(table: pd.DataFrame, prefix: str = "224") -> pd.DataFrame:
    """Convert numbers written as text ("17, 5") into floats in all columns.

    The ID column is skipped, so IDs stay exactly as they are
    (22423021 must not become 22423021.0).
    Returns a new table; the original one is not changed.
    """
    id_column = find_id_column(table, prefix)
    result = table.copy()
    for column in result.columns:
        if column != id_column:
            result[column] = result[column].map(to_number)
    return result.infer_objects()


def validate_table(table: pd.DataFrame, prefix: str = "224") -> list[str]:
    """Check a cleaned table and return a list of problems (empty = all good).

    Checks:
      * every ID starts with `prefix` and appears only once;
      * every grade (columns to the right of the ID) is a number from 0 to 20
        or NaN -- no leftover text.
    Row numbers in the messages are Excel row numbers.
    """
    problems = []
    id_column = find_id_column(table, prefix)
    ids = table[id_column].map(normalize_id)

    for row, student_id in ids.items():
        if student_id is None or not student_id.startswith(prefix):
            problems.append(f"row {row + 1}: bad ID {student_id!r}")

    for row, student_id in ids[ids.duplicated(keep=False)].items():
        problems.append(f"row {row + 1}: ID {student_id} appears more than once")

    grade_columns = [column for column in table.columns if column > id_column]
    for column in grade_columns:
        for row, value in table[column].items():
            if pd.isna(value):
                continue
            if isinstance(value, str) or isinstance(value, bool):
                problems.append(
                    f"row {row + 1}, column {column}, ID {ids[row]}: "
                    f"not a number {value!r}"
                )
            elif not 0 <= value <= 20:
                problems.append(
                    f"row {row + 1}, column {column}, ID {ids[row]}: "
                    f"grade {value} is outside 0-20"
                )

    return problems


def clean_table(table: pd.DataFrame, prefix: str = "224", check: bool = True) -> pd.DataFrame:
    """Full preprocessing of one grade sheet read with header=None.

    1. keep_student_rows -- drop the header, empty rows, group average;
    2. mark_missing      -- "abs", "ab", " " ... -> NaN;
    3. fix_numbers       -- "17, 5" -> 17.5;
    4. validate_table    -- if check=True, raise ValueError listing
                            all problems found.
    Returns a new table; the original one is not changed.
    """
    table = keep_student_rows(table, prefix)
    table = mark_missing(table)
    table = fix_numbers(table, prefix)

    if check:
        problems = validate_table(table, prefix)
        if problems:
            raise ValueError(
                f"{len(problems)} problem(s) in the table:\n" + "\n".join(problems)
            )
    return table


def read_sheet(path: str | Path, sheet: str | None = None) -> pd.DataFrame:
    """Read one grade sheet "as is", without a header (header=None).

    path  -- .xlsx / .xls / .csv file
    sheet -- Excel sheet name, e.g. "CS". May be omitted if the file
             has only one sheet. Ignored for .csv files.

    Raises a clear error if the file does not exist, the format is not
    supported, or the sheet is missing / ambiguous.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No such file: {path}")

    suffix = path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(path, header=None)

    if suffix in {".xlsx", ".xls"}:
        with pd.ExcelFile(path) as workbook:
            sheets = workbook.sheet_names
            if sheet is None:
                if len(sheets) != 1:
                    raise ValueError(
                        f"{path.name} has several sheets {sheets}; pass sheet="
                    )
                sheet = sheets[0]
            elif sheet not in sheets:
                raise ValueError(
                    f"{path.name} has no sheet {sheet!r}; available: {sheets}"
                )
            return workbook.parse(sheet, header=None)

    raise ValueError(f"Unsupported file format {suffix!r}: {path.name}")


def to_assignment_table(table: pd.DataFrame, grade_column: int, prefix: str = "224") -> pd.DataFrame:
    """Turn a cleaned grade sheet into a table of one assignment.

    table        -- result of clean_table()
    grade_column -- position of the grade column in the original sheet,
                    0-based (A=0, B=1, C=2, ...). Cleaning keeps the
                    original column numbers, so count as in Excel.

    Returns a table with:
      * index "student_id" -- IDs as strings ("22423021");
      * one column "grade" -- float, NaN for missing grades.
    """
    id_column = find_id_column(table, prefix)

    if grade_column not in table.columns:
        raise ValueError(
            f"No column {grade_column}; available: {list(table.columns)}"
        )
    if grade_column == id_column:
        raise ValueError(f"Column {grade_column} is the ID column, not grades")

    result = pd.DataFrame({
        "student_id": table[id_column].map(normalize_id),
        "grade": table[grade_column].astype(float),
    })
    return result.set_index("student_id")


def parse_assignment(
    path: str | Path,
    grade_column: int,
    sheet: str | None = None,
    prefix: str = "224",
) -> pd.DataFrame:
    """Full pipeline for one assignment: file -> table "student_id | grade".

    read_sheet -> clean_table -> to_assignment_table.
    See to_assignment_table for the meaning of `grade_column`.
    """
    table = read_sheet(path, sheet)
    table = clean_table(table, prefix)
    return to_assignment_table(table, grade_column, prefix)
