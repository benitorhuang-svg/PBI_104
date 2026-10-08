"""Build native M contract checks from complete query exports, without API calls."""

import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / ".optimization/probes/staging.pq"


def function(name):
    code = (ROOT / f"powerquery/archive/pre-db-etl/03_staging/{name}.pq").read_text(encoding="utf-8")
    return "(jobs as table) => let stg_Jobs = jobs, Result = (" + code + ") in Result"


def main():
    code = '''let
    Serialize = (value as any) => Text.FromBinary(Json.FromValue(value), TextEncoding.Utf8),
    Skills = SKILLS,
    Categories = CATEGORIES,
    MustFail = (operation as function) as logical => (try Serialize(operation()))[HasError],
    Raw = Table.FirstN(src_104Jobs, 1),
    Stage = Table.Buffer(stg_Jobs),
    Empty = fxStageJobs(Table.FirstN(src_104Jobs, 0)),
    Fixture = Json.Document(Binary.FromText("FIXTURE", BinaryEncoding.Base64)),
    FixtureRecords = List.Transform(Fixture[data], (job) => Record.Combine({
        Record.TransformFields(job, List.Transform(Record.FieldNames(job), each {_, (value) =>
            if Value.Is(value, type record) or Value.Is(value, type list) then Serialize(value) else value})),
        [snapshotDate = "2026-08-13", snapshotDateTime = "2026-08-13T12:00:00+08:00",
         sourceKeyword = "powerbi", sourceArea = "fixture", sourcePage = 1, sourcePageSize = 20]})),
    FixtureStage = fxStageJobs(Table.FromRecords(FixtureRecords)),
    BadSalary = fxStageJobs(Table.TransformColumns(Raw, {{"salaryLow", each "invalid"}})),
    BadDate = fxStageJobs(Table.TransformColumns(Raw, {{"appearDate", each "20260230"}})),
    Duplicate = Table.Combine({Raw, Table.TransformColumns(Raw, {{"sourcePage", each 99}})}),
    PddDrift = Table.Combine({Raw, Table.TransformColumns(Raw, {{"pddScore", each if _ = null then 0 else _ + 1}})}),
    Conflict = Table.Combine({Raw, Table.TransformColumns(Raw, {{"jobName", each "CONFLICT"}})}),
    BadKey = Table.TransformColumns(Raw, {{"jobNo", each null}}),
    BadSkillShape = Table.TransformColumns(Stage, {{"pcSkillsRaw", each "{}"}}),
    BadSkillKey = Table.TransformColumns(Table.FirstN(Stage, 1), {{"pcSkillsRaw", each "[{\"\"description\"\":\"\"x\"\"}]"}}),
    BadCategory = Table.TransformColumns(Table.FirstN(Stage, 1), {{"jobCatRaw", each "[1.5]"}}),
    NoSkills = Table.TransformColumns(Stage, {{"pcSkillsRaw", each "[]"}}),
    Checks = [
        malformedJsonRejected = MustFail(() => fxParseJsonList("[", "pcSkills")),
        wrongShapeRejected = MustFail(() => Skills(BadSkillShape)),
        missingSkillCodeRejected = MustFail(() => Skills(BadSkillKey)),
        fractionalCategoryRejected = MustFail(() => Categories(BadCategory)),
        fractionalIntegerRejected = MustFail(() => fxStrictNumber(1.5, true)),
        nullJobRejected = MustFail(() => fxStageJobs(BadKey)),
        conflictingJobRejected = MustFail(() => fxStageJobs(Conflict)),
        identicalJobCollapsed = Table.RowCount(fxStageJobs(Duplicate)) = 1,
        unmodeledPddScoreDriftCollapsed = Table.RowCount(fxStageJobs(PddDrift)) = 1,
        invalidSalaryRecorded = BadSalary{0}[salaryLow] = null and Text.Contains(BadSalary{0}[qualityIssues], "salaryLow"),
        invalidDateRecorded = BadDate{0}[appearDate] = null and BadDate{0}[appearDateQuality] = "invalid",
        emptyJobs = Table.RowCount(Empty) = 0,
        emptySkills = Table.RowCount(Skills(Empty)) = 0 and Table.RowCount(Skills(NoSkills)) = 0,
        emptyCategories = Table.RowCount(Categories(Empty)) = 0,
        fixtureSkillPairs = Table.RowCount(Skills(FixtureStage)) = 107,
        fixtureCategoryPairs = Table.RowCount(Categories(FixtureStage)) = 52,
        areaKeysConsistent = List.Count(List.Difference(List.Distinct(Stage[areaKey]), stg_Areas[areaKey])) = 0
    ],
    Passed = List.AllTrue(Record.FieldValues(Checks)),
    Result = [passed = Passed, checks = Checks, jobs = Table.RowCount(Stage),
        skills = Table.RowCount(stg_JobSkills), categories = Table.RowCount(stg_JobCategories),
        history = Table.RowCount(stg_JobHistory), quality = Table.ToRecords(stg_DataQuality)],
    Output = if Passed then #table(type table [Result = text], {{Serialize(Result)}}) else
        error Error.Record("Stage contract failed", Serialize(Checks), Checks)
in Output
'''
    code = code.replace("SKILLS", function("stg_JobSkills")).replace("CATEGORIES", function("stg_JobCategories"))
    fixture = (ROOT / "tools/tests/fixtures/api-response-page-1.fixture.json").read_bytes()
    code = code.replace("FIXTURE", base64.b64encode(fixture).decode("ascii"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(code, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
