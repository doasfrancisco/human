import * as vscode from "vscode"
import { FranppState } from "../state"

export class HumanCodeLensProvider implements vscode.CodeLensProvider {
  private readonly emitter = new vscode.EventEmitter<void>()
  readonly onDidChangeCodeLenses = this.emitter.event

  constructor(private readonly state: FranppState) {}

  refresh(): void {
    this.emitter.fire()
  }

  provideCodeLenses(): vscode.CodeLens[] {
    const range = new vscode.Range(0, 0, 0, 0)
    const files = this.state.current()
    const traced = files ? files.contextProvenance.length + files.pythonProvenance.length : 0
    return [
      new vscode.CodeLens(range, { command: "franpp.compile", title: "$(zap) Compile" }),
      new vscode.CodeLens(range, { command: "franpp.reword", title: "$(edit) Reword file" }),
      new vscode.CodeLens(range, { command: "", title: `$(references) ${traced} provenance ${traced === 1 ? "entry traces" : "entries trace"} out of this file` }),
    ]
  }

  dispose(): void {
    this.emitter.dispose()
  }
}
