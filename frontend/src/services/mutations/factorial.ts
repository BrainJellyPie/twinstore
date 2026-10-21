import { mutationOptions } from "@tanstack/react-query";
import { exportFactorial, previewFactorial, type FactorialRequest } from "@/shared/api/factorial";

export const factorialPreview = (pid: string, eid: string) => mutationOptions({ mutationFn: (req: FactorialRequest) => previewFactorial(pid, eid, req) });
export const factorialExport = (pid: string, eid: string) => mutationOptions({ mutationFn: (req: FactorialRequest) => exportFactorial(pid, eid, req) });
