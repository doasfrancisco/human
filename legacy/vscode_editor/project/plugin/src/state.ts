import * as vscode from "vscode"
import { FilesResponse } from "./api"

export class FranppState {
  private readonly emitter = new vscode.EventEmitter<FilesResponse>()
  private latest: FilesResponse | undefined

  readonly onDidChange: vscode.Event<FilesResponse> = this.emitter.event

  current(): FilesResponse | undefined {
    return this.latest
  }

  update(files: FilesResponse): void {
    this.latest = files
    this.emitter.fire(files)
  }

  dispose(): void {
    this.emitter.dispose()
  }
}
