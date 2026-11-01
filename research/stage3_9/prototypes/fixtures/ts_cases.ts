/**
 * TypeScript Synthetic Parser & Resolution Fixture
 * Covers 6 required constructs for LFCG extraction and resolution:
 * 1. Named and default imports
 * 2. Aliases
 * 3. Classes and methods
 * 4. Arrow functions
 * 5. Re-exports
 * 6. Structural typing
 */

// 1. Named and default imports & 2. Aliases
import DefaultService, { helperUtil, queryData as queryAlias } from './external_module';

// 5. Re-exports
export { queryAlias, helperUtil };
export * from './reexported_module';

// 4. Arrow functions as top-level definitions
export const computeHash = (data: string): string => {
    return `hash:${data}`;
};

export const transformPayload = (obj: Record<string, unknown>) => {
    const raw = JSON.stringify(obj);
    return computeHash(raw);
};

// 3. Classes and methods
export class PipelineOrchestrator {
    private stageId: string;

    constructor(stageId: string) {
        this.stageId = stageId;
    }

    public runStage(): boolean {
        return this.internalValidate();
    }

    private internalValidate(): boolean {
        return this.stageId.length > 0;
    }
}

// 6. Structural typing interfaces
export interface ITaskRunner {
    executeTask(cmd: string): Promise<number>;
}

export interface IBackupRunner {
    executeTask(cmd: string): Promise<number>;
}

// Callers:

// 1 & 2. Named, default, and aliased imports
export function callerImportedApis(): void {
    const service = new DefaultService();
    helperUtil("arg1");
    queryAlias("query_key");
}

// 3. Class method invocations
export function callerClassMethods(): boolean {
    const orchestrator = new PipelineOrchestrator("stage-1");
    return orchestrator.runStage();
}

// 4. Arrow function calls
export function callerArrowInvocation(): string {
    return transformPayload({ key: "val" });
}

// 6. Structural typing dispatch
export async function callerStructuralDispatch(runner: ITaskRunner): Promise<number> {
    // Structural type: runner could be any object conforming to ITaskRunner
    return await runner.executeTask("start");
}

