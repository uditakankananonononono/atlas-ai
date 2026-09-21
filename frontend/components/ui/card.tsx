import * as React from "react";
import {cn} from "../../lib/utils";
export const Card=React.forwardRef<HTMLDivElement,React.HTMLAttributes<HTMLDivElement>>(({className,...props},ref)=><div ref={ref} className={cn("rounded-xl border border-slate-700 bg-slate-900",className)} {...props}/>);Card.displayName="Card";
export const CardHeader=({className,...props}:React.HTMLAttributes<HTMLDivElement>)=><div className={cn("p-4 pb-2",className)} {...props}/>;
export const CardContent=({className,...props}:React.HTMLAttributes<HTMLDivElement>)=><div className={cn("p-4 pt-2",className)} {...props}/>;
