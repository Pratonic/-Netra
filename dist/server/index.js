export default {
  async fetch(request, env) {
    if (!env.AEGIS_ORIGIN || !env.AEGIS_GATEWAY_SECRET) return new Response('Aegis service is awaiting AWS deployment.', {status:503});
    const url=new URL(request.url);
    const viewer=request.headers.get('oai-authenticated-user-id');
    if (!viewer) return new Response('Sign in to this private workspace to continue.',{status:401});
    if (!['GET','HEAD','POST','PUT','PATCH','DELETE'].includes(request.method)) return new Response('Method not allowed',{status:405});
    if (!['GET','HEAD'].includes(request.method)) {
      const origin=request.headers.get('origin');
      if (origin!==url.origin || request.headers.get('sec-fetch-site')==='cross-site') return new Response('Invalid request origin',{status:403});
      if (Number(request.headers.get('content-length')||0)>350000) return new Response('Request too large',{status:413});
    }
    const headers=new Headers();
    for(const key of ['accept','content-type','cookie','x-csrf-token'])if(request.headers.has(key))headers.set(key,request.headers.get(key));
    headers.set('x-aegis-gateway',env.AEGIS_GATEWAY_SECRET);
    headers.set('x-aegis-viewer',viewer);
    try {
      const origin=new URL(env.AEGIS_ORIGIN);
      origin.pathname=url.pathname;origin.search=url.search;
      const response=await fetch(origin.toString(),{method:request.method,headers,body:['GET','HEAD'].includes(request.method)?undefined:request.body,redirect:'manual',signal:AbortSignal.timeout(28000)});
      const output=new Response(response.body,response);
      output.headers.set('Referrer-Policy','strict-origin-when-cross-origin');
      output.headers.set('X-Content-Type-Options','nosniff');
      output.headers.set('Permissions-Policy','camera=(self), microphone=(), geolocation=()');
      output.headers.set('Content-Security-Policy',"default-src 'self'; script-src 'self' 'wasm-unsafe-eval' blob: https://*.cloudfront.net https://cdn.jsdelivr.net https://unpkg.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' blob: data: https://*.amazonaws.com; media-src 'self' blob:; connect-src 'self' https://*.amazonaws.com wss://*.amazonaws.com https://*.cloudfront.net https://cdn.jsdelivr.net https://unpkg.com https://tfhub.dev https://*.kaggle.com https://storage.googleapis.com; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'");
      if(url.pathname.startsWith('/api/'))output.headers.set('Cache-Control','no-store');
      return output;
    } catch {return Response.json({error:'Cloud connection lost. No automatic access is granted.'},{status:503,headers:{'Cache-Control':'no-store'}});}
  }
};
