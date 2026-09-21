import {createClient} from "@supabase/supabase-js";
const url=process.env.NEXT_PUBLIC_SUPABASE_URL;
const key=process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
export const supabase=url&&key?createClient(url,key,{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:true}}):null;
export async function authFetch(input:RequestInfo|URL,init:RequestInit={}){
 const session=supabase?(await supabase.auth.getSession()).data.session:null;
 const headers=new Headers(init.headers);
 if(session?.access_token)headers.set("Authorization",`Bearer ${session.access_token}`);
 return fetch(input,{...init,headers});
}
