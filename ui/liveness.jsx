import React from 'react';
import {createRoot} from 'react-dom/client';
import {FaceLivenessDetectorCore} from '@aws-amplify/ui-react-liveness';
import {ThemeProvider} from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
export function mountLiveness(element,session,onComplete,onError){const root=createRoot(element);const c=session.credentials;root.render(<ThemeProvider><FaceLivenessDetectorCore sessionId={session.sessionId} region={session.region} onAnalysisComplete={onComplete} onError={onError} onUserCancel={()=>onError({message:'Live check cancelled.'})} config={{credentialProvider:async()=>({...c,expiration:new Date(c.expiration)})}}/></ThemeProvider>);return()=>root.unmount();}
