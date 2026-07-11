import { FilesResponse, programName, ProvenanceEntry } from "../api"

export function defaultPythonTarget(files: FilesResponse | undefined): string {
  return `${programName(files)}.py`
}

export type PhraseRange = { start: number; end: number }

export type PhraseLineMatch = { phrase: string; line: number; target: string | null }

export type PositionedPhraseMatch = PhraseLineMatch & { range: PhraseRange }

export function humanPhrasesFromSource(source: string): string[] {
  return [...source.matchAll(/human phrase "([^"]+)"/g)].map((match) => match[1]).filter(Boolean)
}

export function phraseRanges(text: string, phrase: string): PhraseRange[] {
  const ranges: PhraseRange[] = []
  if (!phrase) return ranges
  const lowerText = text.toLowerCase()
  const lowerPhrase = phrase.toLowerCase()
  let index = lowerText.indexOf(lowerPhrase)
  while (index !== -1) {
    ranges.push({ start: index, end: index + phrase.length })
    index = lowerText.indexOf(lowerPhrase, index + 1)
  }
  return ranges
}

export function phraseRangeAtPosition(text: string, phrase: string, pos: number): PhraseRange | undefined {
  return phraseRanges(text, phrase).find((range) => pos >= range.start && pos <= range.end)
}

export function provenancePhraseMatches(entries: ProvenanceEntry[]): PhraseLineMatch[] {
  return entries.flatMap((entry) =>
    humanPhrasesFromSource(entry.source).map((phrase) => ({
      phrase,
      line: Number(entry.line),
      target: entry.target ?? null,
    }))
  )
}

export function narrowestPhraseMatchesAt(humanText: string, entries: ProvenanceEntry[], pos: number): PositionedPhraseMatch[] {
  return provenancePhraseMatches(entries)
    .flatMap((match) => {
      if (!Number.isFinite(match.line)) return []
      const range = phraseRangeAtPosition(humanText, match.phrase, pos)
      return range ? [{ ...match, range }] : []
    })
    .sort(
      (a, b) =>
        a.range.end - a.range.start - (b.range.end - b.range.start) ||
        a.phrase.length - b.phrase.length ||
        a.range.start - b.range.start
    )
}

export function linesForPhrase(entries: ProvenanceEntry[], phrase: string): number[] {
  const lower = phrase.toLowerCase()
  return Array.from(
    new Set(
      provenancePhraseMatches(entries)
        .filter((match) => match.phrase.toLowerCase() === lower && Number.isFinite(match.line))
        .map((match) => match.line)
    )
  ).sort((a, b) => a - b)
}

export function lineMatchesForPhrase(entries: ProvenanceEntry[], phrase: string): PhraseLineMatch[] {
  const lower = phrase.toLowerCase()
  const seen = new Set<string>()
  return provenancePhraseMatches(entries).filter((match) => {
    if (match.phrase.toLowerCase() !== lower || !Number.isFinite(match.line)) return false
    const key = `${match.target ?? ""}:${match.line}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export function keepNarrowest(ranges: PhraseRange[]): PhraseRange[] {
  return ranges.filter(
    (range) =>
      !ranges.some(
        (other) =>
          other.start >= range.start &&
          other.end <= range.end &&
          other.end - other.start < range.end - range.start
      )
  )
}

export function originRangesForPhrases(humanText: string, phrases: string[]): PhraseRange[] {
  const seen = new Set<string>()
  const ranges: PhraseRange[] = []
  for (const phrase of phrases) {
    for (const range of phraseRanges(humanText, phrase)) {
      const key = `${range.start}:${range.end}`
      if (seen.has(key)) continue
      seen.add(key)
      ranges.push(range)
    }
  }
  return keepNarrowest(ranges)
}

export function entriesForContextLine(entries: ProvenanceEntry[], line: number): ProvenanceEntry[] {
  return entries.filter((entry) => Number(entry.line) === line)
}

export function entriesForPythonLine(
  entries: ProvenanceEntry[],
  line: number,
  target: string,
  fallbackTarget: string
): ProvenanceEntry[] {
  return entries.filter((entry) => Number(entry.line) === line && (entry.target ?? fallbackTarget) === target)
}
