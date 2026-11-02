
function SmtpConfigModal({onClose, onUpdated}){
 const [form,setForm]=useState({host:'',port:587,username:'',password:'',from_email:'',reply_to:'',redirect_email:'',use_ssl:false,imap_host:'',imap_port:993,imap_username:'',imap_password:'',imap_use_ssl:true});
 const [loading,setLoading]=useState(true);
 const [saving,setSaving]=useState(false);
 const [testing,setTesting]=useState(false);
 const [testingInbox,setTestingInbox]=useState(false);
 const [testEmail,setTestEmail]=useState('');
 const [msg,setMsg]=useState(null);

 useEffect(()=>{
  sourcingApi.getSmtpStatus().then(({data})=>{
   setForm(f=>({...f,host:data.host||'',port:data.port||587,username:data.username||'',from_email:data.from_email||'',reply_to:data.reply_to||data.imap_username||data.username||'',redirect_email:'',imap_host:data.imap_host||'',imap_port:data.imap_port||993,imap_username:data.imap_username||data.username||'',imap_password:'',imap_use_ssl:true}));
   setTestEmail(data.from_email||data.username||'');
   setLoading(false);
  }).catch(()=>setLoading(false));
 },[]);

 const applyPreset=(preset)=>{
  if(preset==='gmail'){
   setForm(f=>({...f,host:'smtp.gmail.com',port:587,use_ssl:false,imap_host:'imap.gmail.com',imap_port:993,imap_use_ssl:true,from_email:f.from_email||f.username,imap_username:f.imap_username||f.username}));
   setMsg({type:'info',text:'Gmail preset applied: Use your Gmail address and a 16-character App Password (from myaccount.google.com/apppasswords).'});
  } else if(preset==='outlook'){
   setForm(f=>({...f,host:'smtp.office365.com',port:587,use_ssl:false,imap_host:'outlook.office365.com',imap_port:993,imap_use_ssl:true,from_email:f.from_email||f.username,imap_username:f.imap_username||f.username}));
   setMsg({type:'info',text:'Outlook / Office 365 preset applied.'});
  } else if(preset==='brevo'){
   setForm(f=>({...f,host:'smtp-relay.brevo.com',port:587,use_ssl:false}));
   setMsg({type:'info',text:'Brevo / Sendinblue preset applied.'});
  }
 };

 const handleSave=async(e)=>{
  e.preventDefault();
  setSaving(true);setMsg(null);
  try{
   const {data}=await sourcingApi.saveSmtpConfig(form);
   setMsg({type:'success',text:data.message||'SMTP configuration saved and activated.'});
   if(onUpdated)onUpdated(data.status);
  }catch(err){
   setMsg({type:'error',text:err.response?.data?.detail||err.message||'Failed to save configuration.'});
  }finally{setSaving(false);}
 };

 const handleTest=async()=>{
  setTesting(true);setMsg(null);
  try{
   const {data}=await sourcingApi.testSmtp({to_email:testEmail.trim()||undefined});
   setMsg({type:'success',text:data.message});
  }catch(err){
   setMsg({type:'error',text:err.response?.data?.detail||err.message||'SMTP test failed. Check host, port, and credentials.'});
  }finally{setTesting(false);}
 };

 const handleTestInbox=async()=>{
  setTestingInbox(true);setMsg(null);
  try{const {data}=await sourcingApi.testInbox();setMsg({type:'success',text:data.message});}
  catch(err){setMsg({type:'error',text:err.response?.data?.detail||err.message||'Inbox check failed. Check IMAP settings.'});}
  finally{setTestingInbox(false);}
 };

 return <div className="vp-modal-overlay" onClick={onClose}><div className="vp-modal-card" onClick={e=>e.stopPropagation()}>
  <div className="vp-modal-header">
   <div><Settings size={18}/><strong>SMTP Mail Provider Configuration</strong></div>
   <button className="vp-modal-close" onClick={onClose}>×</button>
  </div>
  <p className="vp-modal-desc">Configure the sourcing sender and reply inbox. Replies use the monitored inbox address. These settings are separate from OTP/login mail. RFQ drafts are saved per purchase; selected drafts send only after reviewer confirmation.</p>
  
  <div className="vp-presets">
   <span>Quick Presets:</span>
   <button type="button" className="vp-preset-btn" onClick={()=>applyPreset('gmail')}>Gmail (smtp.gmail.com)</button>
   <button type="button" className="vp-preset-btn" onClick={()=>applyPreset('outlook')}>Outlook (office365)</button>
   <button type="button" className="vp-preset-btn" onClick={()=>applyPreset('brevo')}>Brevo</button>
  </div>

  <form onSubmit={handleSave} className="vp-smtp-form">
   <div className="vp-form-row-2">
    <label>SMTP Host *<input required placeholder="smtp.gmail.com" value={form.host} onChange={e=>setForm({...form,host:e.target.value})}/></label>
    <label>Port *<input type="number" required placeholder="587" value={form.port} onChange={e=>setForm({...form,port:Number(e.target.value)})}/></label>
   </div>
   <div className="vp-form-row-2">
    <label>Username / Login Email *<input required placeholder="you@domain.com" value={form.username} onChange={e=>setForm({...form,username:e.target.value})}/></label>
    <label>Password / App Password<input type="password" placeholder="Leave blank to keep saved password" value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/><small>Required only for the first setup or when changing the password.</small></label>
   </div>
   <div className="vp-form-row-2">
    <label>From Sender Email<input value="prepares23@gmail.com" readOnly/><small>Supplier RFQs are sent from this dedicated mailbox only.</small></label>
    <div className="vp-mailbox-note"><small>RFQs go directly to the selected vendor contact after a human approves each email. No demo or redirect delivery is used.</small></div>
   </div>
   <label className="vp-checkbox-label">
    <input type="checkbox" checked={form.use_ssl} onChange={e=>setForm({...form,use_ssl:e.target.checked})}/>
    <span>Use SSL / TLS connection directly (port 465)</span>
   </label>

   <div className="vp-mailbox-section">
    <strong>Reply inbox (IMAP)</strong>
    <small>SMTP verifies sending. IMAP is separately required to receive supplier replies. For non-Gmail or non-Outlook mail, enter the provider's IMAP host.</small>
    <div className="vp-form-row-2">
     <label>IMAP Host *<input required placeholder="imap.gmail.com" value={form.imap_host} onChange={e=>setForm({...form,imap_host:e.target.value})}/></label>
     <label>Port *<input type="number" required value={form.imap_port} onChange={e=>setForm({...form,imap_port:Number(e.target.value)})}/></label>
    </div>
    <small>Supplier replies will be addressed to <b>{form.imap_username||form.username||'the configured inbox username'}</b> (Reply-To).</small>
    <div className="vp-form-row-2">
     <label>Inbox username<input placeholder="Same as SMTP login if shared" value={form.imap_username} onChange={e=>setForm({...form,imap_username:e.target.value})}/></label>
     <label>Inbox password / app password<input type="password" placeholder="Leave blank to keep saved inbox password" value={form.imap_password} onChange={e=>setForm({...form,imap_password:e.target.value})}/></label>
    </div>
    <label className="vp-checkbox-label"><input type="checkbox" checked={form.imap_use_ssl} onChange={e=>setForm({...form,imap_use_ssl:e.target.checked})}/><span>Use IMAP over SSL (usually port 993)</span></label>
   </div>

   {msg&&<div className={`vp-form-alert alert-${msg.type}`}>{msg.text}</div>}

   <div className="vp-modal-footer">
    <div className="vp-test-group">
     <input className="vp-test-input" placeholder="Test recipient email" value={testEmail} onChange={e=>setTestEmail(e.target.value)}/>
     <button type="button" className="vp-btn vp-btn-outline" disabled={testing||!form.host||!form.username} onClick={handleTest}>
      {testing?'Testing…':'Send Test Email'}
     </button>
     <button type="button" className="vp-btn vp-btn-outline" disabled={testingInbox||!form.imap_host||!form.imap_username} onClick={handleTestInbox}>
      {testingInbox?'Checking…':'Test Reply Inbox'}
     </button>
    </div>
    <div style={{display:'flex',gap:8}}>
     <button type="button" className="vp-btn vp-btn-outline" onClick={onClose}>Cancel</button>
     <button type="submit" className="vp-btn vp-btn-primary" disabled={saving||!form.host||!form.username}>
      {saving?'Connecting…':'Save & Activate'}
     </button>
    </div>
   </div>
  </form>
 </div></div>;
}

import React,{useEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {Plus,Send,Trash2,Upload,CheckCircle2,AlertCircle,RefreshCw,GitBranch,Globe,ExternalLink,Search,Building2,Mail,Star,Trophy,Activity,Loader,Settings,FileText,Check,ShieldCheck,DollarSign,TrendingDown,Award,FileCheck,FileDown,Maximize2,Minimize2,Eye,EyeOff,Table,X} from 'lucide-react';
import {sourcingApi} from '../api/client';
import './Sourcing.css';
import './IntakeChat.css';
import {SourcingDashboard, VendorRecord} from '../components/VendorCRM';
import './VendorCRM.css';

const PAYMENT_TERMS=['PIA (payment in advance)','Net 0','Net 7','Net 10','Net 15','Net 30','Net 45','Net 60','Net 90','Other','Unknown'];
const VENDORS=['Garvita','Ishita','Apoorwa','Anajli'];
const CURRENCIES=[['INR','Indian Rupee'],['USD','US Dollar'],['EUR','Euro'],['GBP','British Pound'],['AED','UAE Dirham'],['AUD','Australian Dollar'],['CAD','Canadian Dollar'],['SGD','Singapore Dollar'],['JPY','Japanese Yen']];
const GOODS_CATEGORIES=['IT hardware','Software and licences','Office supplies','Furniture','Electrical and electronics','MRO (maintenance, repair, operations)','Facilities consumables','Packaging','Raw materials and components','Vehicles and equipment','Lab and medical','Uniforms and merchandise','Print and marketing material'];
const SERVICE_CATEGORIES=['Professional services','IT services','Facility services','Logistics and transport','Travel and events','Marketing and advertising','Telecom and utilities','Insurance and finance','Training and staffing','Repairs and construction'];
const BUYING_METHODS=['Catalog buying','Quote request (RFQ)','Subscription or contract','Tender or project'];
const SERVICE_UNITS=['Hour','Day','Week','Month','Year','Fixed fee','Project'];
const SERVICE_CHECKS=['Service acceptance / sign-off','Usage or activation record','Progress certificate'];
const DATA_TYPES=['Confidential Business Information','Company Financial Data','Marketing Data','Personal Data (e.g. name, email, location, etc.)'];
const categoryOptions=type=>type==='Services'?SERVICE_CATEGORIES:type==='Goods'?GOODS_CATEGORIES:['Analytics Software','Software and licences'];
const methodHelp=method=>({'Catalog buying':'For standard repeat items with a known price.','Quote request (RFQ)':'For order-specific prices; compare supplier quotes.','Subscription or contract':'Track contract dates, renewals, and activation or usage.','Tender or project':'This needs manual procurement review; the agent will not automate tenders.'}[method]||'');
const blankItem=()=>({description:'',line_type:'Item',quantity:1,unit_price:'',item_category:'',department:'Sales',project:'Project X',location:'San Francisco - US',contract_start:'',contract_end:'',purchasing_method:'Catalog buying',service_unit:'',service_level:'',acceptance_owner:'',verification_method:'Goods receipt'});
const errorText=e=>typeof e.response?.data?.detail==='string'?e.response.data.detail:e.message||'Check the required fields and try again.';
const lineTotal=item=>(Number(item.quantity)||0)*(Number(item.unit_price)||0);
function PixelBot(){return <svg className="buying-bot" viewBox="0 0 64 64" role="img" aria-label="Buying assistant bot" shapeRendering="crispEdges"><path fill="#ff8fbd" d="M29 2h6v6h-6zM23 8h18v6H23z"/><path fill="#6673de" d="M13 15h38v30H13zM7 21h6v20H7zM51 21h6v20h-6zM19 45h26v7H19z"/><path fill="#353c76" d="M19 13h26v5H19zM13 18h6v27h-6zM45 18h6v27h-6zM19 52h8v7h-8zM37 52h8v7h-8zM13 59h14v4H13zM37 59h14v4H37z"/><path fill="#d8f7ff" d="M19 19h26v24H19z"/><path fill="#4851a5" d="M23 26h6v7h-6zM35 26h6v7h-6zM26 36h12v3H26z"/><path fill="#ff9abd" d="M29 48h6v3h-6z"/></svg>}
function WorkflowMindMap({workflow}){
 if(!workflow?.nodes?.length)return null;
 const nodes=workflow.nodes, edges=workflow.edges||[];
 const indegree=Object.fromEntries(nodes.map(node=>[node.id,0])), levels=Object.fromEntries(nodes.map(node=>[node.id,0]));
 edges.forEach(edge=>{if(indegree[edge.target]!==undefined)indegree[edge.target]+=1;});
 const queue=nodes.filter(node=>indegree[node.id]===0).map(node=>node.id);
 while(queue.length){const id=queue.shift();edges.filter(edge=>edge.source===id).forEach(edge=>{levels[edge.target]=Math.max(levels[edge.target],levels[id]+1);indegree[edge.target]-=1;if(indegree[edge.target]===0)queue.push(edge.target);});}
 const columns=[...new Set(nodes.map(node=>levels[node.id]))].sort((a,b)=>a-b).map(level=>nodes.filter(node=>levels[node.id]===level));
 const cardW=276,cardH=180,gapX=140,gapY=72,pad=40;
 const width=Math.max(820,pad*2+columns.length*cardW+Math.max(0,columns.length-1)*gapX);
 const height=Math.max(560,...columns.map(column=>pad*2+column.length*cardH+Math.max(0,column.length-1)*gapY));
 const positions={};columns.forEach((column,col)=>{const colHeight=column.length*cardH+Math.max(0,column.length-1)*gapY;column.forEach((node,index)=>{positions[node.id]={x:pad+col*(cardW+gapX),y:(height-colHeight)/2+index*(cardH+gapY)};});});
 return <div className="workflow-map-scroll" role="region" aria-label="Generated purchase approval workflow" tabIndex="0"><div className="workflow-map" style={{width,height}}>
  <svg className="workflow-map-edges" width={width} height={height} aria-hidden="true"><defs><marker id="workflow-arrow" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 z" fill="#9a8aae"/></marker></defs>{edges.map((edge,index)=>{const from=positions[edge.source],to=positions[edge.target];if(!from||!to)return null;const x1=from.x+cardW,y1=from.y+cardH/2,x2=to.x,y2=to.y+cardH/2,curve=Math.max(38,(x2-x1)*.48);return <g key={`${edge.source}-${edge.target}-${index}`}><path d={`M ${x1} ${y1} C ${x1+curve} ${y1}, ${x2-curve} ${y2}, ${x2} ${y2}`} markerEnd="url(#workflow-arrow)"/>{edge.label&&<text x={(x1+x2)/2} y={(y1+y2)/2-8}>{edge.label}</text>}</g>;})}</svg>
  {nodes.map((node,index)=>{const tasks=node.review_tasks?.length?node.review_tasks:[{title:'Review this checkpoint',instructions:node.detail}];const assignee=node.assignee,detailOnLeft=(positions[node.id]?.x||0)>width-cardW-40;return <article key={node.id} tabIndex="0" aria-label={`${node.label}. Hover or focus to view review details.`} className={`workflow-map-card kind-${node.kind} workflow-map-has-detail`} style={{left:positions[node.id]?.x,top:positions[node.id]?.y}}><div className="workflow-map-card-top"><span className="workflow-map-index">{index+1}</span><span className={`workflow-map-kind ${node.kind}`}>{node.kind}</span></div><h4>{node.label}</h4><p>{node.detail}</p><div className="workflow-map-owner"><span aria-hidden="true">♙</span>{node.owner_group}</div><section className={`workflow-map-detail ${detailOnLeft?'workflow-map-detail-left':''}`} aria-label={`${node.label} details`}><header><div><small>{node.kind==='control'?'CONTROL STEP':node.kind==='document'?'DOCUMENT REVIEW':'REVIEW STEP'}</small><h5>{node.label}</h5></div><span className="workflow-detail-status">Planned</span></header><p className="workflow-detail-description">{node.detail}</p><div className="workflow-detail-meta"><div><span aria-hidden="true">♙</span><p><small>Responsible reviewer</small><strong>{assignee?.name||node.owner_group||'Role assignment required'}</strong>{assignee?.role&&<small>{assignee.role}{assignee.is_backup?' · backup owner':''}</small>}</p></div><div><span aria-hidden="true">▦</span><p><small>Due date / SLA</small><strong>{node.sla_label||'Set by the assigned approver'}</strong></p></div></div><p className="workflow-detail-sla">Proposed checkpoint · a human reviewer makes the decision.</p><div className="workflow-detail-divider"/><h6>Review tasks <span>({tasks.length})</span></h6><ol>{tasks.map((task,taskIndex)=><li key={`${node.id}-${taskIndex}`}><span>{taskIndex+1}</span><div><strong>{task.title}</strong><small>{task.instructions}</small></div></li>)}</ol><div className="workflow-detail-actions"><button type="button" disabled>Approve</button><button type="button" disabled>Reject</button><button type="button" disabled>Request more info</button></div><small className="workflow-detail-footnote">Actions become available after the request is submitted and a reviewer is assigned.</small></section></article>})}
 </div></div>;
}
function IntakeChat({row,busy,onSend,error,openSignal,privacyHelp}){
 const [text,setText]=useState(''),[open,setOpen]=useState(false),[position,setPosition]=useState(null),[dragging,setDragging]=useState(false);
 const panelRef=useRef(null),dragRef=useRef(null);
 useEffect(()=>{if(openSignal>0)setOpen(true)},[openSignal]);
 const submit=async e=>{e.preventDefault();const message=text.trim();if(!row||!message||busy)return;if(await onSend(message))setText('');};
 const startDrag=e=>{if(e.button!==0||e.target.closest('button'))return;const rect=panelRef.current?.getBoundingClientRect();if(!rect)return;e.preventDefault();dragRef.current={x:e.clientX,y:e.clientY,left:rect.left,top:rect.top};setPosition({left:rect.left,top:rect.top});setDragging(true);e.currentTarget.setPointerCapture(e.pointerId);};
 const moveDrag=e=>{if(!dragRef.current)return;const rect=panelRef.current?.getBoundingClientRect();const width=rect?.width||360,height=rect?.height||480;setPosition({left:Math.max(8,Math.min(window.innerWidth-width,dragRef.current.left+e.clientX-dragRef.current.x)),top:Math.max(8,Math.min(window.innerHeight-height,dragRef.current.top+e.clientY-dragRef.current.y))});};
 const stopDrag=()=>{dragRef.current=null;setDragging(false);};
 return createPortal(<div className="p-buying-assistant-root">{open?<section ref={panelRef} className={`p-intake-chat-window ${dragging?'is-dragging':''}`} style={position?{left:position.left,top:position.top,right:'auto',bottom:'auto'}:undefined} aria-label="Gemini buying assistant">
  <header className="p-intake-chat-header" onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={stopDrag} onPointerCancel={stopDrag}><div className="p-intake-bot-small"><PixelBot/></div><div className="p-intake-chat-title"><strong>Buying assistant</strong><small>Gemini · drag to move</small></div><button type="button" aria-label="Minimize buying assistant" onClick={()=>setOpen(false)}>−</button></header>
  <div className="p-intake-chat-body">{!row&&<p className="p-muted">Preparing this purchase…</p>}{privacyHelp&&<aside className="p-privacy-help"><strong>What does sharing personal data mean?</strong><p>It means a supplier may receive information that identifies a person, such as a name, email address, location, or user activity. For example, a software provider may need user names to create accounts; a delivery provider may need a recipient name and address. Share only what the service needs, and ask your privacy or security team if you are unsure.</p><a href="/sample-vendor-data-sharing-policy.pdf" target="_blank" rel="noreferrer">Read the sample data access policy ↗</a><small>Demonstration sample only; this is not an approved company policy.</small></aside>}{row?.messages?.length>0?<div className="p-intake-chat-history" aria-live="polite">{row.messages.slice(-8).map((message,index)=><article key={`${row.id}-${row.version}-${index}`} className={`sourcing-message ${message.role}`}><strong>{message.role==='assistant'?'Buying assistant':'You'}</strong><p>{message.text}</p></article>)}</div>:!privacyHelp&&<div className="p-intake-chat-welcome"><PixelBot/><strong>Need help with this purchase?</strong><span>Ask for help describing requirements, comparing options, or completing the form.</span></div>}{busy&&<p className="p-muted" role="status">Gemini is thinking…</p>}{error&&<p className="p-notice p-danger" role="alert">{error}</p>}</div>
  <form className="p-intake-chat-composer" onSubmit={submit}><input aria-label="Ask Gemini to help with this purchase" placeholder="Ask Gemini about this purchase…" disabled={busy||!row} value={text} onChange={e=>setText(e.target.value)} maxLength={4000}/><button className="p-button primary" type="submit" disabled={busy||!row||!text.trim()} aria-label="Send message">{busy?<span>…</span>:<Send size={15}/>}</button></form>
 </section>:<button className="p-buying-assistant-launcher" type="button" aria-label="Open Gemini buying assistant" onClick={()=>setOpen(true)}><span className="p-buying-assistant-launcher-bot"><PixelBot/></span><span className="p-buying-assistant-launcher-label">Ask Gemini</span></button>}</div>,document.body);
}
function SourcingAgentReview({run,selected,setSelected,busy,onSend,onReply,sendDisabledReason,onAddVendor,onExternalSearch,onSendAiRfqs,onAnalyze,onRunUpdated,rowId}){
 const [replyDrafts,setReplyDrafts]=useState({});
 const [searchQuery,setSearchQuery]=useState('');
 const [searching,setSearching]=useState(false);
 const [showAddCustom,setShowAddCustom]=useState(false);
 const [customVendor,setCustomVendor]=useState({name:'',website:'',linkedin_url:'',email:'',notes:''});
 const [showSmtpModal,setShowSmtpModal]=useState(false);
 const [rfqEdits,setRfqEdits]=useState({});
 const [reviewingRfqs,setReviewingRfqs]=useState({});
 const [counterEdits,setCounterEdits]=useState({});
 const [sendingCounter,setSendingCounter]=useState({});
 const [checkingInbox,setCheckingInbox]=useState(false);
 const [inboxResult,setInboxResult]=useState(null);
 const [showDiscovery,setShowDiscovery]=useState(false);
 const [analyzing,setAnalyzing]=useState(false);
 const [negotiating,setNegotiating]=useState(false);
 const [negotiationReport,setNegotiationReport]=useState(run?.summary?.negotiation_report||null);
 const [activePanelTab,setActivePanelTab]=useState('vendors'); // 'vendors' | 'compliance'
 const [liveActivities,setLiveActivities]=useState([]);
 const [expandedView,setExpandedView]=useState({}); // { [vendorId]: 'rfq' | 'quote' | 'reply' | 'negotiate' }
 const [lastPollAt,setLastPollAt]=useState(null);
 const [isSeparateView,setIsSeparateView]=useState(false);
 const [isCompact,setIsCompact]=useState(false);
 const [vendorChannel,setVendorChannel]=useState({}); // { [vendorId]: 'email' | 'call' }
 const [vendorEmailTab,setVendorEmailTab]=useState({}); // { [vendorId]: 'progress' | 'negotiation' }
 const [expandedVendor,setExpandedVendor]=useState(null);
 const [vendorPage,setVendorPage]=useState(()=>window.location.hash);
 const vendorBase=`#sourcing/${run?.id}/vendor/`;
 const goVendor=(id,suffix='')=>{window.location.hash=`${vendorBase}${encodeURIComponent(id)}${suffix}`;};
 useEffect(()=>{const update=()=>setVendorPage(window.location.hash);window.addEventListener('hashchange',update);return()=>window.removeEventListener('hashchange',update);},[]);

 const sseRef=useRef(null);
 const pollRef=useRef(null);
 const pollingRef=useRef(false);

 useEffect(()=>{
  if(!isSeparateView) return;
  const onKey=e=>{if(e.key==='Escape')setIsSeparateView(false);};
  window.addEventListener('keydown',onKey);
  return ()=>window.removeEventListener('keydown',onKey);
 },[isSeparateView]);

 useEffect(()=>{
  if(run?.summary?.negotiation_report){
   setNegotiationReport(run.summary.negotiation_report);
  }
 },[run?.summary?.negotiation_report]);

 useEffect(()=>{
  if(!run?.id||!rowId)return;
  if(sseRef.current)sseRef.current.close();
  const es=new EventSource(`/api/v1/sourcing/${rowId}/agent/runs/${run.id}/activity-stream`);
  sseRef.current=es;
  es.onmessage=e=>{try{const msg=JSON.parse(e.data);if(msg.type==='activity')setLiveActivities(prev=>[msg,...prev].slice(0,50));if(msg.type==='stream_end')es.close();}catch(_){}};
  return()=>{es.close();sseRef.current=null;};
 },[run?.id,rowId]);

 // ── AUTONOMOUS BACKGROUND POLL: every 8s, hit check-inbox which auto-parses + auto-negotiates ──
 useEffect(()=>{
  if(!run?.id||!rowId)return;
  const poll=async()=>{
   if(pollingRef.current)return;
   pollingRef.current=true;
   try{
    const {data}=await sourcingApi.checkInbox(rowId,run.id);
    setLastPollAt(new Date());
    if(data.run&&onRunUpdated)onRunUpdated(data.run);
    if(data.run?.summary?.negotiation_report)setNegotiationReport(data.run.summary.negotiation_report);
   }catch(_){}finally{pollingRef.current=false;}
  };
  poll(); // immediate first run
  const timer=setInterval(poll,8000);
  return()=>{clearInterval(timer);};
 },[run?.id,rowId]);

 if(!run)return null;
 const totalCount=run.vendors.length;
 const sentCount=run.vendors.filter(v=>v.sent_at||v.status==='rfq_sent'||v.status==='reply_received_human_review'||v.status==='negotiation_counteroffer_sent').length;
 const repliedCount=run.vendors.filter(v=>v.reply_text||v.status==='reply_received_human_review'||v.status==='negotiation_counteroffer_sent').length;
 const hasQuotes=repliedCount>0;

 const toggle=id=>setSelected(values=>values.includes(id)?values.filter(v=>v!==id):[...values,id]);
 const toggleAll=()=>{if(selected.length===run.vendors.length)setSelected([]);else setSelected(run.vendors.map(v=>v.id));};
 const count=run.summary||{};
 const tools=count.search_tools||run.search_tools||run.public_web?.search_tools||{};
 const recommendation=count.ai_recommendation;
 const allActivities=[...liveActivities,...(run.timeline||[])].filter((a,i,arr)=>arr.findIndex(x=>x.id===a.id)===i).sort((a,b)=>b.id-a.id);

 const handleSearchSubmit=async e=>{e.preventDefault();const q=searchQuery.trim()||tools.search_query;if(!q||searching||!onExternalSearch)return;setSearching(true);try{await onExternalSearch(q);}finally{setSearching(false);}};
 const handleAddCustom=async e=>{e.preventDefault();if(!customVendor.name.trim()||busy||!onAddVendor)return;await onAddVendor(customVendor);setCustomVendor({name:'',website:'',linkedin_url:'',email:'',notes:''});setShowAddCustom(false);};

 const handleAnalyze=async()=>{if(analyzing)return;setAnalyzing(true);try{const result=await onAnalyze();if(result&&onRunUpdated)onRunUpdated(result.run);}finally{setAnalyzing(false);}};
 const handleRunNegotiation=async()=>{
  if(!run?.id||!rowId||negotiating)return;
  setNegotiating(true);
  try{
   const {data}=await sourcingApi.getNegotiationReport(rowId,run.id);
   setNegotiationReport(data.report);
   if(data.run&&onRunUpdated)onRunUpdated(data.run);
  }catch(err){alert(err.response?.data?.detail||'Failed to run commercial negotiation analysis.');}
  finally{setNegotiating(false);}
 };

 const handleCheckInbox=async()=>{
  if(!run?.id||!rowId||checkingInbox)return;
  setCheckingInbox(true);
  setInboxResult(null);
  try{
   const {data}=await sourcingApi.checkInbox(rowId,run.id);
   setInboxResult(data);
   if(data.run&&onRunUpdated)onRunUpdated(data.run);
   if(data.new_replies_found>0){
    try{
     const negRes=await sourcingApi.getNegotiationReport(rowId,run.id);
     setNegotiationReport(negRes.data.report);
     if(negRes.data.run&&onRunUpdated)onRunUpdated(negRes.data.run);
    }catch(_){}
    alert(`📥 ${data.new_replies_found} new vendor quote reply(ies) imported and parsed! Commercial comparison updated.`);
   }else{
    alert('Inbox checked — no new vendor replies found. Reply to an RFQ email at prepares23@gmail.com and check again.');
   }
  }catch(err){alert(err.response?.data?.detail||'Failed to check inbox. Check IMAP credentials in .env.');}
  finally{setCheckingInbox(false);}
 };

 const handleSendCounteroffer=async(vendor)=>{
  if(!run?.id||!rowId||sendingCounter[vendor.id])return;
  const negData=vendor.offer?.negotiation_data||{};
  const current=counterEdits[vendor.id]||{
   subject: `Commercial Counteroffer: [Ref: AuditAI-R${run.id}-V${vendor.id}] - ${vendor.name}`,
   body: negData.counteroffer_email_draft||'',
   to_email: vendor.email||'',
  };
  if(!current.body.trim())return alert('Counteroffer email message cannot be empty.');
  const toEmail=(current.to_email||vendor.email||'').trim();
  if(!toEmail||!toEmail.includes('@'))return alert('Please enter a valid vendor email address.');

  setSendingCounter(prev=>({...prev,[vendor.id]:true}));
  try{
   const {data}=await sourcingApi.sendCounteroffer(rowId,run.id,vendor.id,{
    subject: current.subject,
    body: current.body,
    to_email: toEmail,
   });
   if(data.run&&onRunUpdated)onRunUpdated(data.run);
   alert(`✅ Strategic counteroffer successfully sent to ${toEmail} via prepares23@gmail.com!`);
  }catch(err){
   alert(err.response?.data?.detail||'Failed to send counteroffer email.');
  }finally{
   setSendingCounter(prev=>({...prev,[vendor.id]:false}));
  }
 };

 const isRfqApproved=vendor=>{const edit=rfqEdits[vendor.id];return Boolean(vendor.rfq_approved)&&(!edit||(edit.subject===vendor.rfq_subject&&edit.body===vendor.rfq_body&&(!edit.to_email||edit.to_email===vendor.email)));};
 const selectedVendors=run.vendors.filter(v=>selected.includes(v.id));
 const selectedApproved=selectedVendors.length>0&&selectedVendors.every(isRfqApproved);
 const handleReviewRfq=async(vendor,approved)=>{
  const current=rfqEdits[vendor.id]||{subject:vendor.rfq_subject||'',body:vendor.rfq_body||'',to_email:vendor.email||''};
  if(!current.subject.trim()||!current.body.trim())return alert('Add an email subject and message before approval.');
  const toEmail = (current.to_email || vendor.email || '').trim();
  if(!toEmail || !toEmail.includes('@')) return alert('Please enter a valid vendor email address.');
  setReviewingRfqs(prev=>({...prev,[vendor.id]:true}));
  try{
   const {data}=await sourcingApi.reviewRfq(rowId,run.id,vendor.id,{
    approved,
    subject:current.subject,
    body:current.body,
    recipient_email:toEmail
   });
   if(onRunUpdated)onRunUpdated(data);
   if(approved){
    alert(`✅ RFQ email successfully sent to ${toEmail} via prepares23@gmail.com!`);
   }
  }catch(err){alert(err.response?.data?.detail||'Could not send the RFQ email. Please check your SMTP settings.');}
  finally{setReviewingRfqs(prev=>({...prev,[vendor.id]:false}));}
 };
 const handleSendSelectedRfqs=async()=>{
  if(!selected.length||!selectedApproved||busy||!onSendAiRfqs)return;
  const names=selectedVendors.map(v=>`${v.name} <${v.email}>`);
  if(!window.confirm(`Send these human-approved RFQ emails from prepares23@gmail.com to the vendor contacts below?\n\n${names.join('\n')}\n\nThis sends real email.`))return;
  try{
   const result=await onSendAiRfqs(selected);
   setSelected([]);
   if(result)alert(`${result.sent_count||0} RFQ email(s) sent.${result.already_sent?.length?` Already sent and skipped: ${result.already_sent.join(', ')}.`:''}`);
  }catch(err){alert(err.response?.data?.detail||'The RFQ batch could not be sent. Check the sourcing mailbox and vendor addresses.');}
 };

 const toggleExpand=(vendorId,type)=>{
  setExpandedView(prev=>({
   ...prev,
   [vendorId]: prev[vendorId]===type ? null : type
  }));
 };

 const renderStatusBadge=status=>{
  const badgeConfig={
   rfq_sent: { label: 'RFQ Sent', cls: 'badge-sent' },
   rfq_send_failed: { label: 'Send Failed', cls: 'badge-failed' },
   reply_received_human_review: { label: 'Quote Received', cls: 'badge-quote' },
   negotiation_counteroffer_sent: { label: '✅ Countered', cls: 'badge-countered' },
   draft_ready: { label: 'Draft Ready', cls: 'badge-draft' },
   public_lead: { label: 'External Lead', cls: 'badge-lead' },
  };
  const cfg=badgeConfig[status]||{label: status.replaceAll('_',' '), cls: 'badge-draft'};
  return <span className={`cv-badge ${cfg.cls}`}>{cfg.label}</span>;
 };

 const complianceItems=[
  { name: 'Business information', status: 'Awaiting response', contact: 'Sally Smith', email: 'sales@evergreen.com', date: '—', hasDoc: false },
  { name: 'Tax details', status: 'Awaiting response', contact: 'Sally Smith', email: 'sales@evergreen.com', date: '—', hasDoc: false },
  { name: 'Payment details', status: 'Awaiting response', contact: 'Sally Smith', email: 'sales@evergreen.com', date: '—', hasDoc: false },
  { name: 'Security and compliance', status: 'Awaiting response', contact: 'Sally Smith', email: 'sales@evergreen.com', date: '—', hasDoc: false },
  { name: 'Environmental, Social, and Governance (ESG)', optional: true, status: 'Awaiting response', contact: 'Sally Smith', email: 'sales@evergreen.com', date: '—', hasDoc: false },
  { name: 'Vendor Security Questionnaire', status: 'Ready for review', contact: 'Rachel Nelson', email: 'rachel.nelson@palm.com', date: 'Sep 11', hasDoc: false },
  { name: 'Supplier Diversity Questionnaire', status: 'Awaiting response', contact: 'Sally Smith', email: 'sales@evergreen.com', date: 'Sep 11', hasDoc: false },
  { name: 'Mutual NDA', status: 'Uploaded', contact: 'Rachel Nelson', email: 'rachel.nelson@palm.com', date: 'Sep 11', hasDoc: true },
  { name: 'SOC 2', status: 'Uploaded', contact: 'Rachel Nelson', email: 'rachel.nelson@palm.com', date: 'Sep 11', hasDoc: true },
  { name: 'SOC 1 Type 2', status: 'Awaiting response', contact: 'Sally Smith', email: 'sales@evergreen.com', date: '—', hasDoc: false },
  { name: 'W-9 / W-8BEN', status: 'Awaiting response', contact: 'Sally Smith', email: 'sales@evergreen.com', date: '—', hasDoc: false }
 ];

 const renderFullPanel = (isDedicated = false) => <section className={`chosen-vendors-panel ${isDedicated ? 'cv-in-dedicated-modal' : ''}`}>
  <SourcingDashboard vendors={run.vendors} activities={allActivities}/>
  {/* ── HEADER ──────────────────────────────────────────────────────── */}
  <div className="cv-header">
   <div>
    <span className="cv-eyebrow">AI SOURCING AGENT · COMMERCIAL INTELLIGENCE</span>
    <h3 className="cv-title">Chosen Vendors &amp; Price Negotiation</h3>
    <p className="cv-subtitle">The AI agent manages commercial vendor outreach, compares incoming quotes against budget, and drafts strategic counteroffers to secure lower pricing.</p>
   </div>
   <div className="cv-header-right-col">
    <div className="cv-metric-chips">
     <div className="cv-chip"><strong>{count.shortlisted_count||run.vendors.length||0}</strong><span>Suppliers</span></div>
     <div className="cv-chip"><strong>{count.sent_count||0}</strong><span>RFQs Sent</span></div>
     <div className="cv-chip"><strong>{count.replied_count||0}</strong><span>Quotes In</span></div>
     <div className="cv-chip"><strong>{count.pending_response_count||0}</strong><span>Pending</span></div>
    </div>
    <div className="cv-view-toggle-row">
     {!isDedicated ? (
      <>
       <button type="button" className="cv-separate-launch-btn" onClick={()=>setIsSeparateView(true)} title="Open table separately in a dedicated, spacious window">
        <Maximize2 size={13}/> Open Table Separately
       </button>
       <button type="button" className="cv-collapse-btn" onClick={()=>setIsCompact(true)} title="Collapse table into clean summary card">
        <EyeOff size={13}/> Collapse Table
       </button>
      </>
     ) : (
      <button type="button" className="cv-separate-launch-btn" onClick={()=>setIsSeparateView(false)} title="Minimize back to purchase form">
       <Minimize2 size={13}/> Minimize to Form
      </button>
     )}
    </div>
   </div>
  </div>

  {/* ── 3-STAGE AUTONOMOUS LIFECYCLE TRACKER ────────────────────────── */}
  <div className="cv-flow-stepper">
   <div className={`cv-step-card ${sentCount===0?'active':sentCount>0?'complete':''}`}>
    <div className="cv-step-badge">{sentCount>0?'✓':'1'}</div>
    <div className="cv-step-info">
     <strong>1. Auto-Dispatched RFQs</strong>
     <small>{sentCount>0?`✅ ${sentCount} of ${totalCount} RFQs auto-sent via SMTP`:'⏳ Agent dispatching RFQ emails…'}</small>
    </div>
   </div>
   <div className="cv-step-chevron">→</div>
   <div className={`cv-step-card ${sentCount>0&&repliedCount===0?'active':repliedCount>0?'complete':'disabled'}`}>
    <div className="cv-step-badge">{repliedCount>0?'✓':'2'}</div>
    <div className="cv-step-info">
     <strong>2. Auto-Extracted Quotations</strong>
     <small>{repliedCount>0?`✅ ${repliedCount} quote(s) parsed from inbox`:'🔄 Polling inbox for replies every 8s…'}</small>
    </div>
   </div>
   <div className="cv-step-chevron">→</div>
   <div className={`cv-step-card ${(recommendation||negotiationReport)&&hasQuotes?'complete':hasQuotes?'active':'disabled'}`}>
    <div className="cv-step-badge">{(recommendation||negotiationReport)&&hasQuotes?'🏆':'3'}</div>
    <div className="cv-step-info">
     <strong>3. Auto-Negotiation &amp; Counteroffers</strong>
     <small>{(recommendation||negotiationReport)&&hasQuotes?'✅ Counteroffers auto-dispatched · winner crowned':hasQuotes?'⏳ Generating &amp; sending counteroffers…':'Active once quotes arrive'}</small>
    </div>
   </div>
  </div>

  {/* ── AI NEGOTIATION & COMMERCIAL COMPARISON REPORT (ACTIVE ONLY AFTER RESPONSES) ── */}
  {hasQuotes&&negotiationReport&&<div className="cv-negotiation-banner">
   <div className="cv-neg-top">
    <div className="cv-neg-badge-line">
     <span className="cv-neg-badge">💼 AI COMMERCIAL NEGOTIATOR</span>
     <span className="cv-neg-mode">{negotiationReport.analysis_mode==='gemini_negotiation_agent'?'Gemini 2.5 Strategic Analysis':'Commercial Rules Engine'}</span>
    </div>
    <h4 className="cv-neg-title">Vendor Price Comparison &amp; Progress Report (Based on Submitted Responses)</h4>
    <p className="cv-neg-summary">{negotiationReport.progress_summary}</p>
   </div>

   <div className="cv-neg-stats-grid">
    <div className="cv-neg-stat-box highlight">
     <span className="stat-label">🏆 Top Economical Vendor</span>
     <strong className="stat-value">{negotiationReport.best_vendor_name||'—'}</strong>
     <small className="stat-note">Quoted ₹{Number(negotiationReport.lowest_price||0).toLocaleString()}</small>
    </div>
    <div className="cv-neg-stat-box green">
     <span className="stat-label">💰 Maximum Cost Savings</span>
     <strong className="stat-value">₹{Number(negotiationReport.max_savings_amount||0).toLocaleString()}</strong>
     <small className="stat-note">{negotiationReport.max_savings_percentage?`-${negotiationReport.max_savings_percentage}% below budget target`:'Within budget target'}</small>
    </div>
    <div className="cv-neg-stat-box">
     <span className="stat-label">🎯 Target Purchase Budget</span>
     <strong className="stat-value">₹{Number(negotiationReport.target_budget||0).toLocaleString()}</strong>
     <small className="stat-note">Approved spending cap</small>
    </div>
    <div className="cv-neg-stat-box">
     <span className="stat-label">📊 Bid Spread</span>
     <strong className="stat-value">₹{Number(negotiationReport.lowest_price||0).toLocaleString()} - ₹{Number(negotiationReport.highest_price||0).toLocaleString()}</strong>
     <small className="stat-note">{negotiationReport.vendors_comparison?.length||repliedCount} quotation(s) evaluated</small>
    </div>
   </div>

   {negotiationReport.negotiation_playbook?.length>0&&<div className="cv-playbook-card">
    <span className="playbook-title">📋 Strategic Negotiation Playbook</span>
    <div className="playbook-steps">
     {negotiationReport.negotiation_playbook.map((step,idx)=><div key={idx} className="playbook-step-item">
      <span className="playbook-num">0{idx+1}</span>
      <p>{step}</p>
     </div>)}
    </div>
   </div>}
  </div>}

  {/* ── AI WINNER RECOMMENDATION BANNER (ACTIVE ONLY AFTER RESPONSES) ── */}
  {hasQuotes&&recommendation&&<div className="cv-winner-banner">
   <div className="cv-winner-icon"><Trophy size={26} color="#d97706"/></div>
   <div className="cv-winner-content">
    <div className="cv-winner-top">
     <span className="cv-winner-pill">🏆 RECOMMENDED WINNER</span>
     <span className="cv-winner-method">{recommendation.analysis_by==='gemini'?'AI Response Evaluation (Gemini 2.5)':'Rules Evaluation'}</span>
    </div>
    <h4 className="cv-winner-name">{recommendation.winner_vendor_name}</h4>
    <p className="cv-winner-summary">{recommendation.recommendation_summary}</p>
    {recommendation.ranked?.length>0&&<details className="cv-winner-details">
     <summary>View detailed commercial scorecard ({recommendation.ranked.length} respondents)</summary>
     <div className="cv-scorecard-grid">
      {recommendation.ranked.map((v,i)=><div key={v.vendor_id} className={`cv-scorecard-item ${i===0?'winner-card':''}`}>
       <div className="cv-scorecard-head">
        <strong>#{i+1} {v.vendor_name}</strong>
        <span className="cv-score-badge">{Math.round(v.score)}/100</span>
       </div>
       <p className="cv-scorecard-reason">{v.reasoning}</p>
       {v.strengths?.length>0&&<ul className="cv-strengths">{v.strengths.map((s,j)=><li key={j}>✓ {s}</li>)}</ul>}
       {v.concerns?.length>0&&<ul className="cv-concerns">{v.concerns.map((c,j)=><li key={j}>⚠️ {c}</li>)}</ul>}
      </div>)}
     </div>
    </details>}
   </div>
  </div>}

  {/* ── ACTION TOOLBAR ──────────────────────────────────────────────── */}
  <div className="cv-toolbar">
   {/* Autonomous status pill — all manual gate buttons removed */}
   <div className="cv-auto-status-pill">
    <span style={{color:'#22c55e',fontSize:18,lineHeight:'1',marginRight:6}}>●</span>
    <span><strong>Autonomous AI Agent Active</strong> · RFQs auto-sent · inbox auto-polled every 8s · counteroffers auto-dispatched</span>
    {lastPollAt&&<small style={{marginLeft:8,opacity:0.65}}>Last synced {lastPollAt.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'})}</small>}
   </div>

   <div className="cv-actions">
    <button type="button" className={`cv-btn ${run.mailbox?.configured?'cv-btn-smtp-on':'cv-btn-secondary'}`} onClick={()=>setShowSmtpModal(true)} title="Configure your SMTP mail provider (Gmail, Outlook, etc.)">
     <Settings size={13}/> {run.mailbox?.configured?'🟢 SMTP Active':'⚙️ SMTP Setup'}
    </button>
    <button type="button" className="cv-btn cv-btn-secondary" onClick={()=>setShowDiscovery(d=>!d)}>
     <Search size={13}/> {showDiscovery?'Hide Discovery':'Discover More'}
    </button>
   </div>
  </div>

  {/* ── SUB-TABS: COMMERCIALS vs COMPLIANCE CHECKLIST ──────────────── */}
  <div className="cv-subtabs">
   <button type="button" className={`cv-subtab-btn ${activePanelTab==='vendors'?'active':''}`} onClick={()=>setActivePanelTab('vendors')}>
    🏢 Commercial Quotes &amp; Negotiations ({run.vendors.length})
   </button>
   <button type="button" className={`cv-subtab-btn ${activePanelTab==='compliance'?'active':''}`} onClick={()=>setActivePanelTab('compliance')}>
    📋 Vendor Compliance &amp; Documents ({complianceItems.length})
   </button>
  </div>

  {/* ── VIEW 1: UNCLUTTERED MODERN VENDOR TABLE ─────────────────────── */}
  {activePanelTab==='vendors'&&(
   <div className="cv-table-container">
    {run.vendors.length===0?<div className="cv-empty-state">
     <Search size={28} color="#9ca3af"/>
     <p>No vendors shortlisted yet. Click "Discover More" to search Google or LinkedIn for suppliers.</p>
    </div>:<table className="cv-table cv-table-spacious">
     <thead>
      <tr>
       <th style={{width:'62%'}}>Vendor / Supplier Name</th>
       <th style={{textAlign:'right'}}>Current Status</th>
      </tr>
     </thead>
     <tbody>
      {run.vendors.map(vendor=>{
       const hasVendorReplied=Boolean(vendor.reply_text||vendor.status==='reply_received_human_review'||vendor.status==='negotiation_counteroffer_sent');
       const hasVendorBeenSent=Boolean(vendor.sent_at||vendor.status==='rfq_sent'||vendor.status==='negotiation_counteroffer_sent'||hasVendorReplied);
       const isWinner=hasVendorReplied&&recommendation?.winner_vendor_id===String(vendor.id);
       const pageBase=`${vendorBase}${encodeURIComponent(vendor.id)}`;
       const isExpanded=vendorPage===pageBase||vendorPage.startsWith(pageBase+'/');
       const channel=vendorPage.startsWith(pageBase+'/call')?'call':vendorPage.startsWith(pageBase+'/email')?'email':'home';
       const emailTab=vendorPage.endsWith('/negotiations')?'negotiation':vendorPage.endsWith('/progress')?'progress':'home';
       const negData=hasVendorReplied?(vendor.offer?.negotiation_data||negotiationReport?.vendors_comparison?.find(v=>String(v.vendor_id)===String(vendor.id))):null;

       let statusBadge;
       if(vendor.status==='negotiation_counteroffer_sent'||negData?.counteroffer_sent){
        statusBadge=<span className="cv-badge badge-countered">✅ Counteroffer Auto-Sent via SMTP</span>;
       }else if(hasVendorReplied){
        statusBadge=<span className="cv-badge badge-quote">📥 Quote Received (₹{Number(vendor.offer?.total_price||vendor.offer?.unit_price||0).toLocaleString()})</span>;
       }else if(hasVendorBeenSent){
        statusBadge=<span className="cv-badge badge-sent">✉️ RFQ Auto-Sent · Awaiting Reply</span>;
       }else{
        statusBadge=<span className="cv-badge badge-draft">⏳ Pending RFQ Dispatch</span>;
       }

       return <React.Fragment key={vendor.id}>
        <tr
         className={`cv-spacious-row ${isExpanded?'row-expanded':''} ${isWinner?'row-winner':''}`}
         onClick={()=>goVendor(vendor.id)}
         style={{cursor:'pointer'}}
        >
         <td className="cv-td-vendor-main">
          <button
           type="button"
           className="cv-vendor-open-btn"
           aria-expanded={isExpanded}
           onClick={e=>{e.stopPropagation();goVendor(vendor.id);}}
          >
           <span className="cv-open-indicator">{isExpanded?'▼':'▶'}</span>
           <strong className="cv-vendor-name-text">{vendor.name}</strong>
           
           {negData?.is_cheaper&&<span className="cv-tag-cheaper">Lowest Quoted</span>}
           {vendor.offer?.is_external&&<span className="cv-tag-ext">External</span>}
          </button>
          <span className="cv-click-hint">View vendor communication pages</span>
         </td>

         <td className="cv-td-status-main" style={{textAlign:'right'}}>
          <div style={{display:'inline-flex',flexDirection:'column',alignItems:'flex-end',gap:6}}>
           {statusBadge}
           {hasVendorReplied&&negData?.diff_percent!=null&&(
            <span className={`cv-savings-tag ${negData.is_cheaper?'tag-cheaper':'tag-over'}`}>
             {negData.is_cheaper?`↓ ₹${Number(negData.savings_amount||0).toLocaleString()} cheaper (-${Math.abs(negData.diff_percent)}%)`:`+${negData.diff_percent}% over budget`}
            </span>
           )}
           {vendor.sent_at&&(
            <small className="cv-sent-time">
             Dispatched {new Date(vendor.sent_at).toLocaleDateString([],{month:'short',day:'numeric'})} at {new Date(vendor.sent_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}
            </small>
           )}
          </div>
         </td>
        </tr>

        {/* ── EXPANDED DETAILS: 2 BARS (CALL vs EMAIL) ── */}
        {isExpanded&&<tr className="cv-expanded-row"><td colSpan={2} style={{padding:'0 28px 28px'}}>
         <div className="cv-expanded-drawer cv-vendor-page" role="region" aria-label={`${vendor.name} ${channel} page`}>
          <header className="cv-vendor-page-header"><button type="button" className="p-button" onClick={()=>{if(channel==='home')window.location.hash='';else if(channel==='email'&&emailTab!=='home')goVendor(vendor.id,'/email');else goVendor(vendor.id);}}>← Back {channel==='home'?'to vendors':channel==='email'&&emailTab!=='home'?'to email':'to vendor'}</button><div><small>VENDOR COMMUNICATIONS</small><h2>{vendor.name}</h2><p>{channel==='home'?'Choose a communication channel':channel==='call'?'Call progress':emailTab==='home'?'Email':emailTab==='progress'?'Current email progress':'Negotiations'}</p></div></header>
          
          {channel==='home'&&<div className="crm-vendor-layout"><aside className="crm-worklist"><small>SUPPLIER WORKLIST</small>{run.vendors.map(v=><button type="button" key={v.id} className={v.id===vendor.id?'active':''} onClick={()=>goVendor(v.id)}><span className="crm-avatar">{v.name.slice(0,1)}</span><span><strong>{v.name}</strong><small>{v.reply_text?'Reply received':v.sent_at?'Awaiting reply':'Draft prepared'}</small></span></button>)}</aside><VendorRecord vendor={vendor} activities={allActivities} onEmail={()=>goVendor(vendor.id,'/email')} onCall={()=>goVendor(vendor.id,'/call')}/></div>}
          {/* LEVEL 1: TWO BARS (CALL PROGRESS vs EMAIL PROGRESS) */}
          <div className="cv-channel-bars" hidden>
           <button
            type="button"
            className={`cv-channel-bar-btn ${channel==='call'?'active':''}`}
            onClick={()=>goVendor(vendor.id,'/call')}
           >
            <span className="cv-bar-icon">📞</span>
            <span>See Vendor's Call Progress</span>
           </button>
           
           <button
            type="button"
            className={`cv-channel-bar-btn ${channel==='email'?'active':''}`}
            onClick={()=>goVendor(vendor.id,'/email')}
           >
            <span className="cv-bar-icon">✉️</span>
            <span>See Vendor's Email Progress</span>
            {hasVendorReplied&&<span className="cv-bar-badge">Quote In</span>}
            {negData?.counteroffer_sent&&<span className="cv-bar-badge done">Countered</span>}
           </button>
          </div>

          {/* ── IF CALL SELECTED: UI PLACEHOLDER AS REQUESTED ── */}
          {channel==='call'&&(
           <div className="cv-call-placeholder-card">
            <div className="cv-call-icon">📞</div>
            <h4>Vendor Voice &amp; Call Intelligence</h4>
            <p>Automated vendor phone outreach, call recording, and real-time audio negotiation transcripts will appear here.</p>
            <div className="cv-call-status-pill">
             <span>Not connected</span> · <em>Calling integration will be added here.</em>
            </div>
           </div>
          )}

          {/* ── IF EMAIL SELECTED: 2 SUB-BARS (CURRENT PROGRESS vs NEGOTIATIONS) ── */}
          {channel==='email'&&(
           <div className="cv-email-section">
            
            {/* LEVEL 2: TWO SUB-BARS */}
            <div className="cv-email-sub-bars" hidden={emailTab!=='home'}>
             <button
              type="button"
              className={`cv-email-sub-bar-btn ${emailTab==='progress'?'active':''}`}
              onClick={()=>goVendor(vendor.id,'/email/progress')}
             >
              <span className="cv-sub-dot">●</span>
              <span>See Current Progress (Outbound RFQ &amp; Reply Status)</span>
             </button>

             <button
              type="button"
              className={`cv-email-sub-bar-btn ${emailTab==='negotiation'?'active':''}`}
              onClick={()=>goVendor(vendor.id,'/email/negotiations')}
             >
              <span className="cv-sub-dot">💼</span>
              <span>See for Negotiations (Commercial Comparison &amp; Counteroffers)</span>
              {negData?.counteroffer_sent&&<span className="cv-sub-pill-done">Countered</span>}
             </button>
            </div>

            {/* ── SUB-BAR 1: SEE CURRENT PROGRESS ── */}
            {emailTab==='progress'&&(
             <div className="cv-sub-content">
              
              {/* 1. CURRENT MAIL GIVEN TO THE VENDOR */}
              <div className="cv-progress-mail-card">
               <div className="cv-progress-card-title">
                <div>
                 <span className="cv-label-mini">OUTBOUND RFQ EMAIL</span>
                 <h5>{vendor.rfq_subject||`Request for quotation: ${vendor.name}`}</h5>
                 <div className="cv-mail-meta-line">
                  <span>From: <strong>prepares23@gmail.com</strong></span>
                  <span>To: <strong>{vendor.email}</strong></span>
                  {vendor.sent_at&&<span>Dispatched: <strong>{new Date(vendor.sent_at).toLocaleString()}</strong></span>}
                 </div>
                </div>
                <span className="cv-badge-smtp-sent">✓ Dispatched via SMTP</span>
               </div>
               <div className="cv-mail-body-display">
                <pre>{vendor.rfq_body||'RFQ body loading…'}</pre>
               </div>
              </div>

              {/* 2. CURRENT STATUS OF THE VENDOR'S EMAIL REPLY */}
              <div className="cv-progress-reply-card">
               <div className="cv-progress-reply-head">
                <div>
                 <span className="cv-label-mini">INBOUND VENDOR QUOTATION</span>
                 <h5>Vendor Email Response Status</h5>
                </div>
                <span className={hasVendorReplied?'cv-badge-quote-received':'cv-badge-pending-reply'}>
                 {hasVendorReplied?'✓ Quotation Received':'⏳ Pending Reply'}
                </span>
               </div>

               {!hasVendorReplied?(
                <div className="cv-pending-reply-banner">
                 <p>⏳ <strong>Pending Reply:</strong> Awaiting commercial quotation response from {vendor.name}.</p>
                 <small>The AI agent automatically checks the monitored inbox (IMAP) every 8 seconds for new vendor replies.</small>
                </div>
               ):(
                <div className="cv-reply-details-wrap">
                 <div className="cv-reply-metrics-grid">
                  <div className="cv-rep-chip">
                   <span>Quoted Price</span>
                   <strong>{vendor.offer?.currency||'INR'} {Number(vendor.offer?.total_price||vendor.offer?.unit_price||0).toLocaleString()}</strong>
                  </div>
                  <div className="cv-rep-chip">
                   <span>Lead Time</span>
                   <strong>{vendor.offer?.lead_time_days!=null?`${vendor.offer.lead_time_days} days`:'Proposed in quote'}</strong>
                  </div>
                  <div className="cv-rep-chip">
                   <span>Warranty</span>
                   <strong>{vendor.offer?.warranty||'1 Year Standard Support'}</strong>
                  </div>
                  <div className="cv-rep-chip">
                   <span>Payment Terms</span>
                   <strong>{vendor.offer?.payment_terms||'Net 30'}</strong>
                  </div>
                 </div>

                 <div className="cv-reply-raw-msg">
                  <span className="cv-reply-raw-title">Actual Received Email Message Text:</span>
                  <pre className="cv-pre-content">{vendor.reply_text}</pre>
                 </div>
                </div>
               )}
              </div>

             </div>
            )}

            {/* ── SUB-BAR 2: SEE FOR NEGOTIATIONS ── */}
            {emailTab==='negotiation'&&(
             <div className="cv-sub-content">
              {!hasVendorReplied?(
               <div className="cv-neg-waiting-card">
                <div className="cv-neg-icon">💼</div>
                <h4>Negotiation Engine Awaiting Quotation</h4>
                <p>As soon as <strong>{vendor.name}</strong> submits their quotation, the AI Commercial Negotiator will immediately compare prices against budget targets and auto-dispatch an executive counteroffer via SMTP.</p>
                <small>Inbox is being polled automatically every 8 seconds.</small>
               </div>
              ):(
               <div className="cv-neg-content-wrap">
                {negData&&(
                 <div className="cv-neg-figures-row">
                  <div className="cv-neg-fig-box">
                   <span>Quoted Price</span>
                   <strong>₹{Number(negData.quoted_price||vendor.offer?.total_price||0).toLocaleString()}</strong>
                  </div>
                  <div className="cv-neg-fig-box">
                   <span>Target Budget</span>
                   <strong>₹{Number(negotiationReport?.target_budget||0).toLocaleString()}</strong>
                  </div>
                  <div className="cv-neg-fig-box highlight">
                   <span>Cost Difference / Savings</span>
                   <strong style={{color:negData.is_cheaper?'#15803d':'#b45309'}}>
                    {negData.is_cheaper?`↓ ₹${Number(negData.savings_amount||0).toLocaleString()} cheaper (-${Math.abs(negData.diff_percent)}%)`:`+${negData.diff_percent}% over budget`}
                   </strong>
                  </div>
                 </div>
                )}

                {negData?.negotiation_tip&&(
                 <div className="cv-neg-tip-box">
                  <span className="cv-tip-badge">💡 Strategic Negotiation Play</span>
                  <p>{negData.negotiation_tip}</p>
                 </div>
                )}

                <div className="cv-counteroffer-card">
                 <div className="cv-counteroffer-head">
                  <div>
                   <span className="cv-label-mini">STRATEGIC COUNTEROFFER EMAIL</span>
                   <h5>{counterEdits[vendor.id]?.subject||`Commercial Counteroffer: [Ref: AuditAI-R${run.id}-V${vendor.id}] - ${vendor.name}`}</h5>
                   <div className="cv-mail-meta-line">
                    <span>Sender: <strong>prepares23@gmail.com</strong></span>
                    <span>Recipient: <strong>{vendor.email}</strong></span>
                    {negData?.counteroffer_sent_at&&(
                     <span>Dispatched: <strong>{new Date(negData.counteroffer_sent_at).toLocaleString()}</strong></span>
                    )}
                   </div>
                  </div>
                  <span className={negData?.counteroffer_sent?'cv-badge-counter-sent':'cv-badge-counter-formulating'}>
                   {negData?.counteroffer_sent?'✅ Auto-Dispatched via SMTP':'⚡ Formulating Counteroffer'}
                  </span>
                 </div>

                 <div className="cv-counter-body-display">
                  <pre>{counterEdits[vendor.id]?.body||negData?.counteroffer_email_draft||'Generating strategic counteroffer draft…'}</pre>
                 </div>

                 <div className="cv-counter-footer-bar">
                  <span>Counteroffer formulated by Fortune 500 Chief Procurement Officer prompt and dispatched via SMTP.</span>
                  <button
                   type="button"
                   className="cv-btn cv-btn-outline cv-btn-sm"
                   disabled={sendingCounter[vendor.id]}
                   onClick={()=>handleSendCounteroffer(vendor)}
                  >
                   {sendingCounter[vendor.id]?'Sending…':'✉️ Re-send / Override Counteroffer'}
                  </button>
                 </div>
                </div>

               </div>
              )}
             </div>
            )}

           </div>
          )}

         </div>
        </td></tr>}
       </React.Fragment>;
      })}
     </tbody>
    </table>}
   </div>
  )}

  {/* ── VIEW 2: VENDOR COMPLIANCE & ONBOARDING CHECKLIST ─────────────── */}
  {activePanelTab==='compliance'&&(
   <div className="cv-compliance-container">
    <div className="cv-comp-nav">
     <span className="cv-comp-link active">Overview</span>
     <span className="cv-comp-link">Request details</span>
     <span className="cv-comp-link">Purchase details</span>
     <span className="cv-comp-link">Documents</span>
     <span className="cv-comp-link">Surveys</span>
     <span className="cv-comp-link">Vendor</span>
     <span className="cv-comp-link">Products</span>
    </div>
    <table className="cv-comp-table">
     <thead>
      <tr>
       <th>Item / Requirement</th>
       <th>Status</th>
       <th>Vendor Contact</th>
       <th>Date</th>
       <th style={{textAlign:'right'}}>Actions</th>
      </tr>
     </thead>
     <tbody>
      {complianceItems.map((item,idx)=>{
       const statusCls=item.status==='Uploaded'?'comp-uploaded':item.status==='Ready for review'?'comp-review':'comp-awaiting';
       return <tr key={idx} className="cv-comp-row">
        <td className="cv-comp-td-name">
         <strong>{item.name}</strong>
         {item.optional&&<small className="cv-comp-opt">Optional</small>}
        </td>
        <td className="cv-comp-td-status">
         <span className={`cv-comp-badge ${statusCls}`}>{item.status}</span>
        </td>
        <td className="cv-comp-td-contact">
         <span className="cv-comp-contact-name">{item.contact}</span>
         <span className="cv-comp-contact-email">{item.email}</span>
        </td>
        <td className="cv-comp-td-date">
         <span>{item.date}</span>
        </td>
        <td className="cv-comp-td-act">
         <div style={{display:'flex',gap:6,justifyContent:'flex-end'}}>
          <button type="button" className="cv-link-btn" title="Flag or note">💬</button>
          {item.hasDoc&&<button type="button" className="cv-link-btn" title="Download Document">↓</button>}
         </div>
        </td>
       </tr>;
      })}
     </tbody>
    </table>
   </div>
  )}

  {/* ── DISCOVERY & ADD SUPPLIER PANEL (TOGGLEABLE) ────────────────── */}
  {showDiscovery&&<div className="cv-discovery-card">
   <div className="cv-disc-head">
    <Globe size={15} color="#6b46c1"/>
    <strong>Market Discovery &amp; Custom Supplier Integration</strong>
   </div>
   <div className="cv-disc-body">
    <form className="cv-disc-form" onSubmit={handleSearchSubmit}>
     <input className="cv-disc-input" placeholder={tools.search_query?`Search Google/LinkedIn for "${tools.search_query}"...`:'Search web for suppliers...'} value={searchQuery} onChange={e=>setSearchQuery(e.target.value)}/>
     <button type="submit" className="cv-btn cv-btn-primary" disabled={searching}>{searching?'Searching…':'Search Web'}</button>
     <button type="button" className="cv-btn cv-btn-secondary" onClick={()=>setShowAddCustom(c=>!c)}>+ Add Custom Supplier</button>
    </form>
    <div className="cv-disc-links">
     {tools.google_search_url&&<a className="cv-ext-link" href={tools.google_search_url} target="_blank" rel="noreferrer"><ExternalLink size={12}/> Google Search</a>}
     {tools.linkedin_search_url&&<a className="cv-ext-link" href={tools.linkedin_search_url} target="_blank" rel="noreferrer"><Building2 size={12}/> LinkedIn Companies</a>}
     {(tools.google_shopping_url||tools.indiamart_search_url)&&<a className="cv-ext-link" href={tools.google_shopping_url||tools.indiamart_search_url} target="_blank" rel="noreferrer"><Search size={12}/> B2B Products</a>}
    </div>
   </div>

   {showAddCustom&&<form className="cv-add-form" onSubmit={handleAddCustom}>
    <h6>Add a Supplier Manually</h6>
    <div className="cv-form-grid-2">
     <label>Company Name *<input required value={customVendor.name} onChange={e=>setCustomVendor({...customVendor,name:e.target.value})} placeholder="e.g. Dell India"/></label>
     <label>Contact Email<input type="email" value={customVendor.email} onChange={e=>setCustomVendor({...customVendor,email:e.target.value})} placeholder="sales@dell.com"/></label>
     <label>Website URL<input value={customVendor.website} onChange={e=>setCustomVendor({...customVendor,website:e.target.value})} placeholder="https://dell.com"/></label>
     <label>LinkedIn URL<input value={customVendor.linkedin_url} onChange={e=>setCustomVendor({...customVendor,linkedin_url:e.target.value})} placeholder="https://linkedin.com/company/dell"/></label>
    </div>
    <div style={{display:'flex',gap:8,marginTop:10}}>
     <button type="submit" className="cv-btn cv-btn-primary" disabled={!customVendor.name.trim()||busy}>Add Supplier to Shortlist</button>
     <button type="button" className="cv-btn cv-btn-secondary" onClick={()=>setShowAddCustom(false)}>Cancel</button>
    </div>
   </form>}
  </div>}

  {/* ── LIVE ACTIVITY FEED (COLLAPSIBLE / CLEAN) ───────────────────── */}
  <details className="cv-activity-details">
   <summary><Activity size={13}/> Live Sourcing Activity Stream ({allActivities.length} events)</summary>
   <div className="cv-activity-list">
    {allActivities.length===0?<p className="cv-activity-none">No events logged yet. Actions like sending RFQs and receiving quotes will appear here.</p>:allActivities.slice(0,10).map(entry=><div key={entry.id} className="cv-activity-item">
     <span className="cv-act-time">{new Date(entry.created_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</span>
     <strong className="cv-act-ev">{entry.event.replaceAll('_',' ')}</strong>
     <span className="cv-act-actor">{entry.actor}</span>
     <small className="cv-act-det">{Object.entries(entry.details||{}).map(([k,v])=>`${k}: ${v}`).join(' · ')}</small>
    </div>)}
   </div>
  </details>

  {showSmtpModal&&<SmtpConfigModal onClose={()=>setShowSmtpModal(false)} onUpdated={(status)=>{if(onRunUpdated&&run){onRunUpdated({...run,mailbox:{...(run.mailbox||{}),...status}});}}}/>}
 </section>;

 return <>
  {/* If compact preview is active and not in separate view */}
  {isCompact && !isSeparateView ? (
   <div><SourcingDashboard vendors={run.vendors} activities={allActivities}/><div className="cv-compact-preview-card">
    <div className="cv-compact-left">
     <div className="cv-compact-icon">
      <Table size={24} color="#6d28d9"/>
     </div>
     <div className="cv-compact-info">
      <div className="cv-compact-tag-line">
       <span className="cv-compact-badge">⚡ COMMERCIAL SOURCING &amp; NEGOTIATION HUB</span>
       <span className="cv-compact-live-dot">● Autonomous AI Loop Active</span>
      </div>
      <h4 className="cv-compact-title">Commercial Sourcing &amp; Price Negotiation Active</h4>
      <p className="cv-compact-desc">
       {repliedCount > 0 ? (
        <>
         <strong>{repliedCount} formal quote(s)</strong> evaluated. Strategic counteroffers auto-dispatched via SMTP.
         {negotiationReport?.best_vendor_name && (
          <> Top proposal: <strong>{negotiationReport.best_vendor_name}</strong> (₹{Number(negotiationReport.lowest_price||0).toLocaleString()}).</>
         )}
        </>
       ) : (
        <>RFQs auto-dispatched to <strong>{sentCount || totalCount} suppliers</strong> via SMTP. Real-time inbox polling active.</>
       )}
      </p>
      <div className="cv-compact-metrics">
       <span className="cv-comp-chip"><strong>{totalCount}</strong> Suppliers</span>
       <span className="cv-comp-chip"><strong>{sentCount}</strong> RFQs Sent</span>
       <span className="cv-comp-chip"><strong>{repliedCount}</strong> Quotes In</span>
       {recommendation?.winner_vendor_name && (
        <span className="cv-comp-chip winner">🏆 Recommended: {recommendation.winner_vendor_name}</span>
       )}
      </div>
     </div>
    </div>
    <div className="cv-compact-actions">
     <button type="button" className="cv-btn-separate-primary" onClick={()=>setIsSeparateView(true)} title="Open table in dedicated spacious window">
      <Maximize2 size={15}/> Open Table Separately
     </button>
     <button type="button" className="cv-btn-inline-link" onClick={()=>setIsCompact(false)}>
      Or view full table inline here ▾
     </button>
    </div>
   </div>
  </div>) : (
   renderFullPanel(false)
  )}

  {/* Dedicated Fullscreen / Modal View */}
  {isSeparateView && createPortal(
   <div className="cv-dedicated-backdrop" onClick={()=>setIsSeparateView(false)}>
    <div className="cv-dedicated-container" onClick={e=>e.stopPropagation()}>
     <div className="cv-dedicated-topbar">
      <div className="cv-dedicated-title-wrap">
       <span className="cv-dedicated-icon">💼</span>
       <div>
        <h4>Commercial Sourcing &amp; Autonomous Price Negotiation</h4>
        <small>Dedicated Workspace · Zero form congestion · Real-time IMAP Polling &amp; Automated SMTP Counteroffers</small>
       </div>
      </div>
      <div className="cv-dedicated-bar-actions">
       <div className="cv-dedicated-pill">
        <span style={{color:'#4ade80',fontSize:14}}>●</span>
        <span>Autonomous AI Agent Active</span>
        {lastPollAt&&<small style={{marginLeft:6,opacity:0.65}}>Synced {lastPollAt.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</small>}
       </div>
       <button type="button" className="cv-dedicated-minimize-btn" onClick={()=>setIsSeparateView(false)}>
        <Minimize2 size={14}/> Minimize to Form
       </button>
       <button type="button" className="cv-dedicated-close-x" onClick={()=>setIsSeparateView(false)} title="Close dedicated view">
        <X size={18}/>
       </button>
      </div>
     </div>
     <div className="cv-dedicated-scroll-body">
      {renderFullPanel(true)}
     </div>
    </div>
   </div>,
   document.body
  )}
 </>;
}

export default function PurchaseIntake({close,Modal}){
 const [row,setRow]=useState(null),[draft,setDraft]=useState({}),[items,setItems]=useState([blankItem()]),[busy,setBusy]=useState(false),[error,setError]=useState(''),[chatError,setChatError]=useState(''),[status,setStatus]=useState('Loading request…'),[result,setResult]=useState(null),[dirty,setDirty]=useState(false),[step,setStep]=useState(0),[assistantOpenSignal,setAssistantOpenSignal]=useState(0),[privacyHelp,setPrivacyHelp]=useState(false),[contractDocs,setContractDocs]=useState([]),[contractFiles,setContractFiles]=useState({}),[workflowResult,setWorkflowResult]=useState(null),[agentRun,setAgentRun]=useState(null),[agentSelection,setAgentSelection]=useState([]);
 const rowRef=useRef(null),draftRef=useRef({}),itemsRef=useRef([blankItem()]);
 const payload=()=>{const lines=itemsRef.current.map(i=>({...i,quantity:Number(i.quantity)||1,unit_price:i.unit_price===''?null:Number(i.unit_price),item_category:i.item_category||null,department:i.department||null,project:i.project||null,location:i.location||null,contract_start:i.contract_start||null,contract_end:i.contract_end||null,purchasing_method:i.purchasing_method||null,service_unit:i.service_unit||null,service_level:i.service_level||null,acceptance_owner:i.acceptance_owner||null,verification_method:i.verification_method||null}));const product=lines.map(i=>i.description).filter(Boolean).join('; ');return {...draftRef.current,product:product||null,quantity:lines.reduce((n,i)=>n+(Number(i.quantity)||0),0),line_items:lines,delivery_deadline:draftRef.current.contract_end||null,delivery_location:lines[0]?.location||null,specifications:draftRef.current.specifications||'None',mandatory_conditions:draftRef.current.mandatory_conditions||'None'};};
 const adopt=r=>{const req={...r.requirements,currency:r.requirements.currency||'INR',purchase_type:r.requirements.purchase_type||'Goods',category:r.requirements.category||'',payment_terms:r.requirements.payment_terms||'Net 30',ai_selects_vendor:r.requirements.ai_selects_vendor??true,data_types:r.requirements.data_types||[],data_sharing_choice:r.requirements.data_sharing_choice||null};const next=Array.isArray(req.line_items)&&req.line_items.length?req.line_items:[blankItem()];rowRef.current={...r,requirements:req};draftRef.current=req;itemsRef.current=next;setRow({...r,requirements:req});setDraft(req);setItems(next);setDirty(false);setStatus('Saved');};
 useEffect(()=>{sourcingApi.create().then(async r=>{adopt(r.data);try{const docs=await sourcingApi.contractDocuments(r.data.id);setContractDocs(docs.data);}catch{}}).catch(e=>setError(errorText(e)));},[]);
 const saveSnapshot=async confirm=>{if(!rowRef.current)throw new Error('The request is still loading.');const snapshot=payload();const {data}=await sourcingApi.save(rowRef.current.id,snapshot,rowRef.current.version,confirm);adopt(data);setStatus('Saved to the backend as structured JSON.');return data;};
 const persist=async()=>{if(JSON.stringify(payload())===JSON.stringify(rowRef.current?.requirements)&&!dirty)return rowRef.current;const data=await saveSnapshot(false);return data;};
 const action=async fn=>{setBusy(true);setError('');try{await fn();return true;}catch(e){setError(errorText(e));return false;}finally{setBusy(false);}};
 const change=(key,value)=>{const next={...draftRef.current,[key]:value===''?null:value};draftRef.current=next;setDraft(next);setDirty(true);setStatus('Unsaved changes');};
 const changeLine=(index,key,value)=>{const next=itemsRef.current.map((item,i)=>i===index?{...item,[key]:value}:item);itemsRef.current=next;setItems(next);setDirty(true);setStatus('Unsaved changes');};
 const total=items.reduce((sum,item)=>sum+lineTotal(item),0),currency=draft.currency||'INR';
 const money=value=>new Intl.NumberFormat('en-IN',{style:'currency',currency,minimumFractionDigits:2}).format(Number(value||0));
 const symbol=new Intl.NumberFormat('en-IN',{style:'currency',currency}).formatToParts(0).find(part=>part.type==='currency')?.value||currency;
 const purchaseIssues=()=>{const issues=[];if(!Number(draftRef.current.budget)||Number(draftRef.current.budget)<=0)issues.push('Enter a positive spending budget.');if(!draftRef.current.category)issues.push('Choose a detailed purchase category.');if(!draftRef.current.contract_start||!draftRef.current.contract_end)issues.push('Enter both contract dates.');if(!draftRef.current.payment_terms)issues.push('Choose payment terms.');if(!itemsRef.current.length)issues.push('Add at least one line item.');itemsRef.current.forEach((item,index)=>{const n=index+1;if(!String(item.description||'').trim())issues.push(`Enter a description for line ${n}.`);if(!item.item_category)issues.push(`Choose a goods or service category for line ${n}.`);if(!item.purchasing_method)issues.push(`Choose how line ${n} will be purchased.`);if(!item.verification_method)issues.push(`Choose how line ${n} will be verified.`);if(!Number(item.quantity)||Number(item.quantity)<1)issues.push(`Enter a quantity for line ${n}.`);if(item.unit_price===''||item.unit_price==null||Number(item.unit_price)<0)issues.push(`Enter an amount for line ${n}.`);if(!item.location)issues.push(`Choose a delivery location for line ${n}.`);if(item.line_type==='Service'){if(!item.service_unit)issues.push(`Choose a service unit for line ${n}.`);if(!item.service_level?.trim())issues.push(`Enter the service level for line ${n}.`);if(!item.acceptance_owner?.trim())issues.push(`Name who will sign off line ${n}.`);}});if(Number(draftRef.current.budget)>0&&total>Number(draftRef.current.budget))issues.push('Line item total is above the spending budget.');return [...new Set(issues)];};
 const saveDraft=()=>action(()=>persist());
 const closeIntake=()=>{if(dirty&&!window.confirm('Discard unsaved changes?'))return;close();};
 const finishRequest=()=>{const issues=purchaseIssues();if(!draft.data_sharing_choice)issues.push('Choose whether personal data will be shared: Yes, No, or I don’t know.');if(draft.shares_personal_data===true&&(!draft.data_types?.length||!draft.data_usage?.trim()))issues.push('Select at least one data type and explain how the supplier will use it.');if(issues.length){setError(issues.join(' '));document.querySelector('.p-intake-main .p-notice.p-danger')?.scrollIntoView({block:'start',behavior:'smooth'});return;}action(async()=>{const saved=await saveSnapshot(true);const {data}=await sourcingApi.startAgent(saved.id);setAgentRun(data);setAgentSelection(data.vendors.filter(v=>!v.synthetic).map(v=>v.id));setResult(data);setStatus(`Agent review ready · ${data.summary.shortlisted_count} supplier matches shortlisted. No email sent.`);setDirty(false);});};
 const sendAgentRFQs=()=>{if(!agentRun||!rowRef.current)return;action(async()=>{if(!window.confirm(`Send the prepared RFQ to ${agentSelection.length} selected verified supplier(s)? This contacts external vendors.`))return;const {data}=await sourcingApi.sendAgentOutreach(rowRef.current.id,agentRun.id,agentSelection);setAgentRun(data);setAgentSelection([]);setStatus(`${data.summary.sent_count} RFQ(s) sent. ${data.summary.pending_response_count} vendor response(s) pending.`);});};
 const recordAgentReply=(vendorId,text)=>{if(!agentRun||!rowRef.current)return;return action(async()=>{const {data}=await sourcingApi.recordAgentReply(rowRef.current.id,agentRun.id,vendorId,text);setAgentRun(data);setStatus(`Supplier reply recorded. ${data.summary.pending_response_count} vendor response(s) still pending.`);});};
 const addCustomVendor=async vendorData=>{if(!agentRun||!rowRef.current)return;return action(async()=>{const {data}=await sourcingApi.addVendor(rowRef.current.id,agentRun.id,vendorData);setAgentRun(data);setStatus(`Vendor "${vendorData.name}" added to shortlist.`);});};
 const runExternalSearch=async query=>{if(!rowRef.current)return;return action(async()=>{const loc=draftRef.current.delivery_location||itemsRef.current[0]?.location||'India';const {data}=await sourcingApi.externalSearch(rowRef.current.id,query,loc);if(agentRun){setAgentRun({...agentRun,public_web:data,summary:{...(agentRun.summary||{}),search_tools:data.search_tools}});};setStatus(`External search finished · ${data.results?.length||0} leads found.`);});};
 const sendAiRfqs=async vendorIds=>{if(!agentRun||!rowRef.current)return;const {data}=await sourcingApi.sendAiRfqs(rowRef.current.id,agentRun.id,vendorIds);setAgentRun(data.run);setStatus(`${data.sent_count} approved RFQ email(s) sent from prepares23@gmail.com to vendor contacts.`);return data;};
 const analyzeVendorResponses=async()=>{if(!agentRun||!rowRef.current)return;const {data}=await sourcingApi.analyzeResponses(rowRef.current.id,agentRun.id);setAgentRun(data.run);setStatus(`AI analysis complete. Recommended vendor: ${data.analysis?.winner_vendor_name||'see results'}`);return data;};
 const workflowPlan=()=>{const serviceItems=items.filter(i=>i.line_type==='Service');const hasService=serviceItems.length>0||draft.purchase_type==='Services';const hasIT=items.some(i=>/IT hardware|software|licen|cloud/i.test(i.item_category||'')||/IT services/i.test(i.item_category||''))||/software/i.test(draft.purchase_type||'');const dataRisk=draft.data_sharing_choice==='yes'||draft.data_sharing_choice==='unknown';const stages=[{name:'Procurement review',reason:'Check the request, category, required evidence, and purchasing route.'},{name:'Department manager / budget owner',reason:'Confirm the business need, budget ownership, and accountable delivery or service owner.'},{name:'Finance approval',reason:'Check the budget, total cost, payment terms, and financial coding.'}];if(hasService)stages.push({name:'Legal review',reason:'Review the MSA and SOW where applicable, including scope, term, liability, and renewal clauses.'});if(hasIT)stages.push({name:'IT review',reason:'Review technical fit, access, integrations, and support requirements.'});if(dataRisk)stages.push({name:'Security and privacy review',reason:draft.data_sharing_choice==='unknown'?'Data sharing is unknown; confirm what information is involved before approval.':'Review the selected data types, vendor use, and safeguards.'});return {stages,hasService,hasIT,dataRisk,serviceItems};};
 const plan=workflowPlan();
 const createWorkflow=async()=>{if(!rowRef.current)return;setBusy(true);setError('');try{await persist();const {data}=await sourcingApi.workflow(rowRef.current.id);setWorkflowResult(data);setStatus(data.source==='gemini'?'Gemini generated this route from your purchase details.':data.notice||'Showing the rules-based workflow route.');return data;}catch(e){setError(errorText(e));return null;}finally{setBusy(false);}};
 const advance=async()=>{
  setError('');if(busy)return;
  if(!rowRef.current){setError('The purchase request is still loading. Please try again in a moment.');return;}
  if(step===0){const issues=purchaseIssues();if(issues.length){setError(issues.join(' '));return;}}
  if(step===1&&!draft.data_sharing_choice){setError('Choose Yes, No, or I don’t know before continuing.');return;}
  if(step===1){
    const workflow=await createWorkflow();
    if(!workflow)return;
    setStep(2);
    if(!agentRun && rowRef.current){
      action(async()=>{
        const saved=await saveSnapshot(true);
        const {data}=await sourcingApi.startAgent(saved.id);
        setAgentRun(data);
        setAgentSelection(data.vendors.map(v=>v.id));
        setResult(data);
        setStatus(`Approval map generated and ${data.vendors?.length||0} vendors shortlisted.`);
      });
    }
    return;
  }
  setStep(Math.min(3,step+1));
 };
 const regenerateWorkflow=async()=>{const workflow=await createWorkflow();if(workflow)setStatus(workflow.source==='gemini'?'Gemini generated an updated route.':workflow.notice||'Updated rules-based route.');};
 const uploadContract=async kind=>{const file=contractFiles[kind];if(!file||!row)return;await action(async()=>{const {data}=await sourcingApi.uploadContractDocument(row.id,kind,file);setContractDocs(docs=>[...docs.filter(d=>d.kind!==kind),data]);setContractFiles(files=>({...files,[kind]:null}));setStatus(`${kind.toUpperCase()} uploaded and stored with this request.`);});};
 const sendChat=async message=>{setBusy(true);setError('');setChatError('');try{await persist();const {data}=await sourcingApi.message(rowRef.current.id,message,rowRef.current.version);adopt(data);return true;}catch(e){const messageText=errorText(e);setError(messageText);setChatError(messageText);return false;}finally{setBusy(false);}};
 return <><Modal title="Request a purchase" close={closeIntake} busy={busy} wide fullscreen><div className="p-stepper intake-fullscreen-marker"><button type="button" className="p-button intake-cancel-request" onClick={closeIntake}>Cancel request</button><span className={step===0?'current':step>0?'complete':''}><b>1</b>Purchase details</span><span className={step===1?'current':step>1?'complete':''}><b>2</b>Data information</span><span className={step===2?'current':step>2?'complete':''}><b>3</b>Approval Map & Sourcing</span><span className={step===3?'current':''}><b>4</b>Review & Submit</span></div><section className="p-intake-main"><section className="p-dialog-body">
 {error&&<p className="p-notice p-danger" role="alert">{error}</p>}{!row?<div className="intake-loading">Loading purchase request…</div>:<>
 {step===0&&<>
 <h3>How much budget will you need for this purchase? <b>*</b></h3>
 <div className="intake-budget"><select aria-label="Currency" value={currency} onChange={e=>change('currency',e.target.value)}>{CURRENCIES.map(([code,name])=><option key={code} value={code}>{code} · {name}</option>)}</select><span>{symbol}</span><input aria-label="Purchase budget" type="text" inputMode="decimal" value={draft.budget||''} placeholder="Enter budget" onChange={e=>change('budget',e.target.value.replace(/[^0-9.]/g,''))}/></div>

 <h3 className="intake-form-heading">Please enter the line item breakdown: <b>*</b></h3>
 {items.map((item,index)=>{const service=item.line_type==='Service';const categories=service?SERVICE_CATEGORIES:GOODS_CATEGORIES;return <article className="intake-line screenshot-line" key={index}>
  <div className="intake-line-head"><strong>Line {index+1}</strong><span>Line total&nbsp; {money(lineTotal(item))}</span>{items.length>1&&<button className="p-icon" type="button" aria-label={`Remove line ${index+1}`} onClick={()=>{const next=itemsRef.current.filter((_,i)=>i!==index);itemsRef.current=next;setItems(next);setDirty(true);setStatus('Unsaved changes');}}><Trash2 size={15}/></button>}</div>
  <div className="p-form-grid intake-description-grid"><label className="p-field intake-wide-field"><span>Description</span><input value={item.description||''} onChange={e=>changeLine(index,'description',e.target.value)}/></label><label className="p-field"><span>Line type</span><select value={item.line_type||'Item'} onChange={e=>{const type=e.target.value;changeLine(index,'line_type',type);changeLine(index,'item_category','');changeLine(index,'purchasing_method',type==='Service'?'Quote request (RFQ)':'Catalog buying');changeLine(index,'verification_method',type==='Service'?'Service acceptance / sign-off':'Goods receipt');change('purchase_type',type==='Service'?'Services':'Goods');change('category','');}}><option>Item</option><option>Service</option></select></label></div>
  <div className="p-form-grid"><label className="p-field"><span>{service?'Quantity (service units)':'Quantity (Each)'}</span><input type="number" min="1" step="1" value={item.quantity??1} onChange={e=>changeLine(index,'quantity',e.target.value)}/></label><label className="p-field"><span>{service?'Rate / amount':'Amount'}</span><div className="intake-amount"><span>{currency}</span><input type="text" inputMode="decimal" value={item.unit_price??''} placeholder="0.00" onChange={e=>changeLine(index,'unit_price',e.target.value.replace(/[^0-9.]/g,''))}/></div></label></div>
  <div className="p-form-grid"><label className="p-field"><span>{service?'Service category':'Goods category'}</span><select value={item.item_category||''} onChange={e=>{changeLine(index,'item_category',e.target.value);if(index===0)change('category',e.target.value);}}><option value="">Select {service?'service':'goods'} category</option>{categories.map(category=><option key={category}>{category}</option>)}</select></label><label className="p-field"><span>Department</span><select value={item.department||''} onChange={e=>changeLine(index,'department',e.target.value)}><option value="">Select department</option><option>Sales</option><option>Finance</option><option>Manager</option><option>IT</option><option>Operations</option></select></label></div>
  <div className="p-form-grid"><label className="p-field"><span>How is it usually bought?</span><select value={item.purchasing_method||''} onChange={e=>changeLine(index,'purchasing_method',e.target.value)}><option value="">Select buying method</option>{BUYING_METHODS.map(method=><option key={method}>{method}</option>)}</select><small>{methodHelp(item.purchasing_method)}</small></label><label className="p-field"><span>How will delivery be verified?</span><select value={item.verification_method||''} onChange={e=>changeLine(index,'verification_method',e.target.value)}>{(service?SERVICE_CHECKS:['Goods receipt (physical count)']).map(method=><option key={method}>{method}</option>)}</select></label></div>
  {service&&<><div className="p-form-grid"><label className="p-field"><span>Service unit</span><select value={item.service_unit||''} onChange={e=>changeLine(index,'service_unit',e.target.value)}><option value="">Select unit</option>{SERVICE_UNITS.map(unit=><option key={unit}>{unit}</option>)}</select></label><label className="p-field"><span>Service level / SLA</span><input value={item.service_level||''} placeholder="Describe the required service level" onChange={e=>changeLine(index,'service_level',e.target.value)}/></label></div><label className="p-field"><span>Who signs off that the service was delivered?</span><input value={item.acceptance_owner||''} placeholder="Role or person responsible" onChange={e=>changeLine(index,'acceptance_owner',e.target.value)}/></label><p className="intake-match-note">Service matching checks the PO, service acceptance or sign-off, and invoice.</p></>}
  {!service&&<p className="intake-match-note">Goods matching checks the PO, physical goods receipt, and invoice.</p>}
  <div className="p-form-grid"><label className="p-field"><span>Project</span><select value={item.project||''} onChange={e=>changeLine(index,'project',e.target.value)}><option value="">Select project</option><option>Project X</option></select></label><label className="p-field"><span>Location</span><select value={item.location||''} onChange={e=>changeLine(index,'location',e.target.value)}><option value="">Select location</option><option>San Francisco - US</option></select></label></div>
  <label className="p-field intake-dates"><span>Contract dates</span><div><input aria-label="Contract start date" type="date" value={item.contract_start||''} onChange={e=>changeLine(index,'contract_start',e.target.value)}/><span>→</span><input aria-label="Contract end date" type="date" value={item.contract_end||''} onChange={e=>changeLine(index,'contract_end',e.target.value)}/></div></label>
 </article>;})}
 <button className="p-link intake-add-line" type="button" onClick={()=>{const next=[...itemsRef.current,blankItem()];itemsRef.current=next;setItems(next);setDirty(true);setStatus('Unsaved changes');}}><Plus size={16}/> Add line item</button>
 <div className="intake-line-total"><span>Line item total ({items.length})</span><strong>{money(total)}</strong></div>

 <label className="p-field intake-select-field"><span>What are you looking to purchase? <b>*</b></span><select value={draft.purchase_type||'Goods'} onChange={e=>{change('purchase_type',e.target.value);change('category','');}}><option>Goods</option><option>Services</option><option>Software</option></select></label>
 <label className="p-field intake-select-field"><span>Which detailed category best describes your purchase? <b>*</b></span><select value={draft.category||''} onChange={e=>change('category',e.target.value)}><option value="">Select a category</option>{categoryOptions(draft.purchase_type||'Goods').map(category=><option key={category}>{category}</option>)}</select></label>

 <section className="intake-vendor-section"><strong>Vendor choice</strong><p>Let the AI recommend a vendor, or mark one supplier as your preference. A preference is a hint, not a restriction.</p><label className="intake-agent-choice"><input type="checkbox" checked={draft.ai_selects_vendor!==false} onChange={e=>change('ai_selects_vendor',e.target.checked)}/><span>Ask the AI to recommend a vendor</span></label><p className="intake-vendor-hint">Optional preferred vendor</p><div className="intake-vendor-list">{VENDORS.map(vendor=><div className={`intake-vendor-row ${draft.preferred_vendors===vendor?'selected':''}`} key={vendor}><span className="intake-vendor-mark" aria-hidden="true">{vendor.slice(0,1)}</span><span>{vendor}</span><button type="button" className="p-button primary" aria-pressed={draft.preferred_vendors===vendor} onClick={()=>{const chosen=draft.preferred_vendors===vendor?'':vendor;change('preferred_vendors',chosen);change('vendor_preference',chosen?'prioritize':'');}}>{draft.preferred_vendors===vendor?'Selected':'Choose'}</button></div>)}</div><small>These four names are examples. A real vendor recommendation needs approved company supplier offers; the AI can suggest a better fit when that data is available.</small></section>

 <h3 className="intake-contract-heading">What is the desired start and end date for this purchase/contract? <b>*</b></h3><label className="p-field intake-dates"><span>Contract dates</span><div><input aria-label="Purchase contract start date" type="date" value={draft.contract_start||''} onChange={e=>change('contract_start',e.target.value)}/><span>→</span><input aria-label="Purchase contract end date" type="date" value={draft.contract_end||''} onChange={e=>change('contract_end',e.target.value)}/></div></label>

 <fieldset className="intake-payment"><legend>Please select the payment terms of this contract: <b>*</b></legend>{PAYMENT_TERMS.map(term=><label key={term}><input type="radio" name="payment_terms" checked={draft.payment_terms===term} onChange={()=>change('payment_terms',term)}/><span>{term}</span></label>)}</fieldset>
 </>}
 {step===1&&<section className="intake-data-information"><h3>Data Information</h3><p>Will any personal data be shared for this engagement? For example, customer emails, names, user activity, etc. <b>*</b></p><p className="p-muted">Please see the attached data policy for detailed descriptions and definitions.</p><div className="intake-policy-links"><a href="/sample-vendor-data-sharing-policy.pdf" target="_blank" rel="noreferrer">Data Access Policy ↗</a><a href="/sample-vendor-data-sharing-policy.pdf" download>Download attachment ↓</a><small>Demonstration sample only; not an approved company policy.</small></div><fieldset className="intake-data-choice"><legend>Will personal data be shared with this supplier?</legend>{[['yes','Yes','Select this if personal data will be shared with the vendor.'],['no','No','Select this if no personal data will be shared with the vendor.'],['unknown',"I don't know",'Select this option if you are unsure.']].map(([value,title,help])=><label key={value}><input type="radio" name="shares_personal_data" checked={draft.data_sharing_choice===value} onChange={()=>{const next={...draftRef.current,data_sharing_choice:value,shares_personal_data:value==='yes'?true:value==='no'?false:null,...(value==='no'?{data_types:[],data_usage:null}:{})};draftRef.current=next;setDraft(next);setPrivacyHelp(value==='unknown');if(value==='unknown')setAssistantOpenSignal(n=>n+1);setDirty(true);setStatus('Unsaved changes');}}/><span><strong>{title}</strong><small>{help}</small></span></label>)}</fieldset>{draft.shares_personal_data===true&&<><fieldset className="intake-data-types"><legend>What type of data/information will be shared? <b>*</b></legend>{DATA_TYPES.map(type=><label key={type}><input type="checkbox" checked={(draft.data_types||[]).includes(type)} onChange={()=>{const values=draft.data_types||[];change('data_types',values.includes(type)?values.filter(v=>v!==type):[...values,type]);}}/><span>{type}</span></label>)}</fieldset><label className="p-field"><span>How will this vendor use this data? <b>*</b></span><textarea maxLength={2000} value={draft.data_usage||''} onChange={e=>change('data_usage',e.target.value)} placeholder="Describe the purpose for sharing this data."/></label></>}</section>}
 {step===2&&<section className="intake-workflow"><div className="intake-workflow-heading"><div><h3>Workflow for this purchase</h3><p>This approval map is tailored to the selected goods or services and data-sharing answers. Each card is a proposed checkpoint for human review.</p></div><button className="p-button" type="button" onClick={regenerateWorkflow} disabled={busy||!row}><RefreshCw size={14} className={busy?'workflow-spinning':''}/>{busy?'Generating…':'Regenerate map'}</button></div><div className="intake-workflow-source"><GitBranch size={15}/><span>{workflowResult?.source==='gemini'?'Generated by Gemini':'Rules-based workflow'}</span><small>{workflowResult?.notice||'Gemini proposes the route; authorized people remain responsible for approvals.'}</small></div>{workflowResult?.graph?<><h4 className="intake-workflow-title">{workflowResult.graph.title}</h4><p className="intake-workflow-summary">{workflowResult.graph.summary}</p><WorkflowMindMap workflow={workflowResult.graph}/></>:<div className="intake-workflow-loading" role="status">Creating the purchase-specific approval map…</div>}{plan.hasService?<section className="intake-contract-docs"><h4>Service contract documents</h4><p>MSA and SOW checks apply to service engagements. Upload the documents you already have; missing items are flagged for Legal review.</p>{[['msa','Master Services Agreement (MSA)'],['sow','Statement of Work (SOW)']].map(([kind,title])=>{const doc=contractDocs.find(d=>d.kind===kind);return <div className="intake-contract-document" key={kind}><div><strong>{title}</strong><small>{doc?<><CheckCircle2 size={14}/> Uploaded: {doc.filename}</>:<><AlertCircle size={14}/> {contractFiles[kind]?.name||'Not provided yet'}</>}</small></div><label className="p-button"><Upload size={14}/> Choose PDF/DOCX<input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={e=>setContractFiles(files=>({...files,[kind]:e.target.files?.[0]||null}))}/></label><button type="button" className="p-button primary" disabled={!contractFiles[kind]||busy} onClick={()=>uploadContract(kind)}>{busy?'Uploading…':'Upload'}</button></div>})}<p className="intake-contract-note">Uploads are stored as supporting evidence. The system does not decide that a contract is legally sufficient; Legal must review it.</p></section>:<div className="intake-no-contract"><strong>MSA / SOW not applicable to this goods request</strong><p>Goods are checked through the purchase order, goods receipt, and invoice. If an item is actually a service, change its line type to Service.</p></div>}<section className="intake-after-approval"><strong>After approval · delivery and invoice check</strong><p>{plan.hasService?'The named service owner signs off against the agreed scope and service level, then Finance matches the PO, acceptance, and invoice.':'The requester confirms the delivered quantity and condition, then Finance matches the PO, goods receipt, and invoice.'}</p></section>{plan.hasIT&&<p className="intake-route-note">An IT review is included because the selected purchase is technology related.</p>}{plan.dataRisk&&<p className="intake-route-note">A Security and Privacy review is included because data sharing is {draft.data_sharing_choice==='unknown'?'unknown':'marked Yes'}.</p>}

  {/* ── CHOSEN VENDORS TABLE (EMBEDDED ON MAP PAGE) ── */}
  <div className="intake-map-divider" />
  <section className="intake-embedded-sourcing">
   <div className="intake-sourcing-head">
    <div>
     <h3>Chosen Suppliers &amp; Commercial Outreach</h3>
     <p>Review the AI-shortlisted vendors below, send automated RFQs via SMTP, and pick your approved supplier.</p>
    </div>
    {!agentRun&&(
     <button type="button" className="p-button primary" onClick={finishRequest} disabled={busy||!row}>
      {busy?'Searching suppliers…':'Search & Shortlist Vendors'}
     </button>
    )}
   </div>

   {agentRun?(
    <SourcingAgentReview
     run={agentRun}
     selected={agentSelection}
     setSelected={setAgentSelection}
     busy={busy}
     onSend={sendAgentRFQs}
     onReply={recordAgentReply}
     onAddVendor={addCustomVendor}
     onExternalSearch={runExternalSearch}
     onSendAiRfqs={sendAiRfqs}
     onAnalyze={analyzeVendorResponses}
     onRunUpdated={setAgentRun}
     rowId={rowRef.current?.id}
    />
   ):(
    <div className="intake-vendors-standby-card">
     <div className="intake-standby-bot"><PixelBot/></div>
     <div>
      <strong>Sourcing Agent Scanning Catalogs &amp; Commercial Discovery...</strong>
      <p>The AI agent is finding eligible approved suppliers and commercial offerings for this purchase.</p>
     </div>
     <button type="button" className="p-button primary" onClick={finishRequest} disabled={busy||!row}>
      {busy?'Scanning…':'Load Shortlisted Suppliers'}
     </button>
    </div>
   )}
  </section>
</section>}
 {step===3&&<section className="intake-review"><h3>Review your purchase request</h3><p className="p-muted">Confirm the brief to start the sourcing agent. It checks the company-approved catalog and public Google Search results, including publicly indexed LinkedIn company pages. Public leads stay unverified; only approved catalog vendors can be considered for human-confirmed outreach.</p><dl><dt>Budget</dt><dd>{money(draft.budget)}</dd><dt>Purchase type</dt><dd>{draft.purchase_type}</dd><dt>Category</dt><dd>{draft.category}</dd><dt>Line items</dt><dd>{items.map((item,i)=><span key={i}>{i>0?', ':''}{item.description} · {item.quantity} × {money(item.unit_price)}</span>)}</dd><dt>Vendor preference</dt><dd>{draft.preferred_vendors||'AI chooses and recommends'}</dd><dt>Payment terms</dt><dd>{draft.payment_terms}</dd><dt>Personal data shared</dt><dd>{draft.shares_personal_data===true?'Yes':draft.shares_personal_data===false?'No':"I don't know"}</dd>{draft.shares_personal_data===true&&<><dt>Data types</dt><dd>{(draft.data_types||[]).join(', ')}</dd><dt>Use</dt><dd>{draft.data_usage}</dd></>}<dt>Approval route</dt><dd>{workflowResult?.graph?.nodes?.map(node=>node.label).join(' → ')||'Generate the workflow from the previous step.'}</dd>{plan.hasService&&<><dt>MSA status</dt><dd>{contractDocs.some(d=>d.kind==='msa')?'Uploaded':'Not provided · Legal follow-up needed'}</dd><dt>SOW status</dt><dd>{contractDocs.some(d=>d.kind==='sow')?'Uploaded':'Not provided · Legal follow-up needed'}</dd></>}</dl>{agentRun?<SourcingAgentReview run={agentRun} selected={agentSelection} setSelected={setAgentSelection} busy={busy} onSend={sendAgentRFQs} onReply={recordAgentReply} onAddVendor={addCustomVendor} onExternalSearch={runExternalSearch} onSendAiRfqs={sendAiRfqs} onAnalyze={analyzeVendorResponses} onRunUpdated={setAgentRun} rowId={rowRef.current?.id}/>:<div className="intake-agent-start"><strong>Start supplier analysis</strong><p>The agent will inspect approved company offers, search public web sources, rank catalog matches, and prepare RFQ drafts. Public web leads are shown separately and are never contacted automatically. Nothing is emailed until you review and confirm approved recipients.</p><button type="button" className="p-button primary" disabled={busy||!!result||!row} onClick={finishRequest}>{busy?'Analyzing catalog and public sources…':'Analyze vendors and public sources'}</button></div>}</section>}
 </>}</section></section>
 <footer className="intake-footer"><button className="p-button" type="button" onClick={()=>step?setStep(step-1):closeIntake()}>{step?'Back':'Cancel'}</button><span role="status">{dirty?'Unsaved changes':status}</span><button className="p-button" type="button" disabled={busy||!row} onClick={saveDraft}>{busy?'Saving…':'Save draft'}</button>{step<3?<button className="p-button primary" type="button" disabled={busy||!row} onClick={advance}>{busy&&step===1?'Generating…':'Next'}</button>:<button className="p-button primary" type="button" disabled={busy||!!result||!row} onClick={finishRequest}>{busy?'Analyzing…':'Analyze company vendors'}</button>}</footer>
 </Modal><IntakeChat row={row} busy={busy} error={chatError} onSend={sendChat} openSignal={assistantOpenSignal} privacyHelp={privacyHelp}/></>;
}
