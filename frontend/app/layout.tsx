import type {ReactNode} from "react";
import "./globals.css";
export const metadata={title:"Atlas AI",description:"Human-controlled AI work platform"};
export default function Layout({children}:{children:ReactNode}){return <html lang="en"><body>{children}</body></html>}
