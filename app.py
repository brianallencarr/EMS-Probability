from pathlib import Path
import io, json
import pandas as pd
import streamlit as st
import altair as alt
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from core import load_clean, load_concurrency, uniques, f, calc, calc_boolean, wilson, notation, MONTH_LABELS, two_proportion_stats

BASE=Path(__file__).resolve().parent
CLEAN=BASE/'data'/'EMS_10yr_Clean_Normalized.csv'
CONC=BASE/'data'/'EMS_10yr_Concurrency_Incident_Level.csv'
ENRICHED=BASE/'data'/'EMS_10yr_Clean_Normalized_Concurrency_Enriched.csv'
LOGO=BASE/'assets'/'jackson_hole_fire_ems_logo.png'

st.set_page_config(page_title='EMS Probability Explorer v3.1.0',page_icon='📊',layout='wide',initial_sidebar_state='collapsed')

@st.cache_data(show_spinner=False)
def get_clean(): return load_clean(CLEAN)
@st.cache_data(show_spinner=False)
def get_conc(): return load_concurrency(CONC)
@st.cache_data(show_spinner=False)
def get_enriched(): return load_clean(ENRICHED)

clean=get_clean(); conc=get_conc(); enriched=get_enriched()


# Mobile-first presentation layer.
st.markdown("""
<style>
:root { --ems-touch: 46px; }
.block-container { max-width: 1180px; padding-top: 1.15rem; padding-bottom: 2.5rem; }
.stButton > button, .stDownloadButton > button { min-height: var(--ems-touch); white-space: normal; line-height: 1.15; font-weight: 600; }
[data-testid="stMetricValue"] { overflow-wrap: anywhere; }
.stTabs [data-baseweb="tab-list"] { gap: .35rem; overflow-x: auto; scrollbar-width: thin; padding-bottom: .25rem; }
.stTabs [data-baseweb="tab"] { min-width: max-content; flex-shrink: 0; height: 44px; padding-left: .85rem; padding-right: .85rem; }
[data-testid="stExpander"] summary { min-height: 44px; }
[data-testid="stDataFrame"] { max-width: 100%; }
@media (max-width: 768px) {
  .block-container { padding-top: .65rem; padding-left: .65rem; padding-right: .65rem; padding-bottom: 2rem; }
  h1 { font-size: 1.72rem !important; line-height: 1.08 !important; }
  h2 { font-size: 1.38rem !important; }
  h3 { font-size: 1.15rem !important; }
  p, li, label { font-size: .96rem; }
  [data-testid="stMetricLabel"] { font-size: .76rem; }
  [data-testid="stMetricValue"] { font-size: 1.58rem; }
  .stTabs [data-baseweb="tab"] { height: 42px; padding-left: .7rem; padding-right: .7rem; font-size: .88rem; }
  [data-testid="stSidebar"] img { max-width: 180px !important; margin-left: auto; margin-right: auto; }
}
</style>
""", unsafe_allow_html=True)


def pdf_bytes(title,subtitle,result,event_labels,condition_labels,source,extra=None):
    buf=io.BytesIO()
    with PdfPages(buf) as pdf:
        fig=plt.figure(figsize=(8.5,11))
        fig.text(.08,.94,title,fontsize=18,weight='bold')
        fig.text(.08,.90,subtitle,fontsize=11)
        p=result.get('probability')
        fig.text(.08,.83,'Observed probability',fontsize=11,weight='bold')
        fig.text(.08,.78,'—' if p is None else f'{p*100:.2f}%',fontsize=28,weight='bold')
        fig.text(.08,.72,f"Numerator: {result.get('numerator',0):,}",fontsize=11)
        fig.text(.08,.69,f"Denominator: {result.get('denominator',0):,}",fontsize=11)
        lo,hi=wilson(result.get('numerator',0),result.get('denominator',0))
        if lo is not None: fig.text(.08,.66,f'95% Wilson CI: {lo*100:.1f}%–{hi*100:.1f}%',fontsize=11)
        y=.59
        fig.text(.08,y,'Event',fontsize=11,weight='bold'); y-=.03
        for lab in event_labels or ['All records']:
            fig.text(.10,y,f'• {lab}',fontsize=10); y-=.025
        y-=.01; fig.text(.08,y,'Given',fontsize=11,weight='bold'); y-=.03
        for lab in condition_labels or ['All records']:
            fig.text(.10,y,f'• {lab}',fontsize=10); y-=.025
        if extra:
            y-=.015; fig.text(.08,y,'Comparison / interpretation',fontsize=11,weight='bold'); y-=.03
            for line in extra:
                fig.text(.10,y,line,fontsize=10); y-=.025
        fig.text(.08,.10,'Source',fontsize=10,weight='bold')
        fig.text(.08,.075,source,fontsize=9)
        fig.text(.08,.045,'A-Shift Data Performance | Insights for Action',fontsize=10,weight='bold')
        plt.axis('off'); pdf.savefig(fig,bbox_inches='tight'); plt.close(fig)
    return buf.getvalue()


def render_result(df,event_filters,condition_filters,source,key_prefix):
    r=calc(df,event_filters,condition_filters); lo,hi=wilson(r['numerator'],r['denominator'])
    st.markdown(f"### {notation(event_filters,condition_filters)}")
    c1,c2=st.columns(2)
    c1.metric('Probability','—' if r['probability'] is None else f"{r['probability']*100:.2f}%")
    c2.metric('95% Wilson CI','—' if lo is None else f'{lo*100:.1f}–{hi*100:.1f}%')
    c3,c4=st.columns(2)
    c3.metric('Numerator',f"{r['numerator']:,}")
    c4.metric('Denominator',f"{r['denominator']:,}")
    if r['denominator'] and r['denominator']<30: st.warning('Small denominator (n < 30): interpret cautiously.')
    elif r['denominator'] and r['denominator']<100: st.info('Moderate denominator (n < 100): confidence interval width matters.')
    with st.expander("Audit / Show Math", expanded=True):
        valid_event_filters = [
            x for x in (event_filters or [])
            if isinstance(x, dict) and x.get("label") not in (None, "", "None")
        ]
        valid_condition_filters = [
            x for x in (condition_filters or [])
            if isinstance(x, dict) and x.get("label") not in (None, "", "None")
        ]

        st.write("**Event:**")
        if valid_event_filters:
            for x in valid_event_filters:
                st.write(f"• {x['label']}")
        else:
            st.write("• All records")

        st.write("**Given:**")
        if valid_condition_filters:
            for x in valid_condition_filters:
                st.write(f"• {x['label']}")
        else:
            st.write("• All records")

        if r["denominator"]:
            st.code(f"P = {r['numerator']} / {r['denominator']} = {r['probability']:.6f}")

        if lo is not None:
            st.markdown("**What the 95% Wilson CI means for chiefs**")
            st.write(
                f"The point estimate is {r['probability']*100:.2f}%; the 95% Wilson interval is "
                f"{lo*100:.1f}%–{hi*100:.1f}%. A narrow interval indicates a comparatively stable estimate; "
                "a wide interval indicates more uncertainty, usually from a smaller denominator or uncommon event."
            )
            st.caption(
                "Frequentist meaning: across repeated samples, about 95% of intervals constructed this way would contain the underlying proportion."
            )

        st.caption(f"Source: {source}. Observed empirical probability; not a causal estimate.")

    payload = {'notation':notation(event_filters,condition_filters),'numerator':r['numerator'],'denominator':r['denominator'],'probability':r['probability'],'wilson95':[lo,hi],'event':event_filters,'conditions':condition_filters,'source':source}
    st.download_button('Download PDF brief',pdf_bytes('EMS Probability Explorer',notation(event_filters,condition_filters),r,[x['label'] for x in event_filters],[x['label'] for x in condition_filters],source),file_name='ems_probability_brief.pdf',mime='application/pdf',key=f'{key_prefix}_pdf',use_container_width=True)
    st.download_button('Download JSON',json.dumps(payload,indent=2),file_name='ems_probability_result.json',mime='application/json',key=f'{key_prefix}_json',use_container_width=True)
    return r

with st.sidebar:
    if LOGO.exists(): st.image(str(LOGO),width=185)
    st.subheader('Dataset')
    st.metric('Normalized records',f'{len(clean):,}')
    st.metric('Unique incident intervals',f'{len(conc):,}')
    st.caption('Concurrency is computed once per distinct incident and joined back to normalized records for combined queries.')
    st.divider(); st.caption('Version 3.1.0 • Mobile optimized')

st.title('EMS Probability Explorer')
st.caption('A-Shift Data Performance | Insights for Action')

tabs=st.tabs(['Quick Buttons','Build a Probability','Boolean Builder','Compare','Temporal Trends','Concurrency','Methods'])

# QUICK BUTTONS
with tabs[0]:
    st.subheader('Quick multi-select')
    st.caption('Selections within a category are OR. Selections across categories are AND.')
    if 'qsel' not in st.session_state:
        st.session_state.qsel={'clinical':[],'performance':[],'gender':[],'weekday':[],'season':[],'time':[],'age':[],'concurrency':[]}
    def toggle(cat,val):
        cur=list(st.session_state.qsel[cat]); cur.remove(val) if val in cur else cur.append(val); st.session_state.qsel[cat]=cur
    def lab(cat,val,text): return ('✓ ' if val in st.session_state.qsel[cat] else '')+text

    st.markdown('**Clinical**')
    clinical=[('Trauma/Injury','Trauma/Injury'),('Cardiac','Cardiac'),('Respiratory','Respiratory'),('Neurologic','Neurologic'),('Endocrine/Metabolic','Endocrine/Metabolic'),('LOC/Syncope','LOC/Syncope'),('Behavioral/Psychiatric','Behavioral/Psychiatric'),('GI/Abdominal','GI/Abdominal')]
    cols=st.columns(2)
    for i,(txt,val) in enumerate(clinical):
        if cols[i%2].button(lab('clinical',val,txt),use_container_width=True,key=f'qc{i}'): toggle('clinical',val); st.rerun()

    st.markdown('**Performance**'); perf=[('Turnout ≤ 2 min','turnout_le_2m'),('Response ≤ 10 min','response_le_10m'),('Scene ≤ 20 min','scene_le_20m'),('Commitment > 90 min','commitment_gt_90m')]
    cols=st.columns(2)
    for i,(txt,val) in enumerate(perf):
        if cols[i%2].button(lab('performance',val,txt),use_container_width=True,key=f'qp{i}'): toggle('performance',val); st.rerun()

    st.markdown('**Gender**'); cols=st.columns(2)
    for i,val in enumerate(['Male','Female','Unspecified']):
        if cols[i%2].button(lab('gender',val,val),use_container_width=True,key=f'qg{i}'): toggle('gender',val); st.rerun()

    st.markdown('**Day / Season**'); days=['Weekend','Monday','Tuesday','Wednesday','Thursday','Friday']; cols=st.columns(2)
    for i,val in enumerate(days):
        if cols[i%2].button(lab('weekday',val,val),use_container_width=True,key=f'qd{i}'): toggle('weekday',val); st.rerun()
    cols=st.columns(2)
    for i,val in enumerate(['Winter','Spring','Summer','Fall']):
        if cols[i%2].button(lab('season',val,val),use_container_width=True,key=f'qs{i}'): toggle('season',val); st.rerun()

    st.markdown('**Time of day**'); tblocks=[('00–04',(0,4)),('04–08',(4,8)),('08–12',(8,12)),('12–16',(12,16)),('16–20',(16,20)),('20–24',(20,24))]; cols=st.columns(2)
    for i,(txt,val) in enumerate(tblocks):
        if cols[i%2].button(lab('time',val,txt),use_container_width=True,key=f'qt{i}'): toggle('time',val); st.rerun()

    st.markdown('**Age**'); ages=[('0–9',(0,9)),('10–17',(10,17)),('18–24',(18,24)),('25–44',(25,44)),('45–64',(45,64)),('65–74',(65,74)),('75–84',(75,84)),('85+',(85,200))]; cols=st.columns(2)
    for i,(txt,val) in enumerate(ages):
        if cols[i%2].button(lab('age',val,txt),use_container_width=True,key=f'qa{i}'): toggle('age',val); st.rerun()

    st.markdown('**Concurrency**'); cols=st.columns(2)
    for i,(txt,val) in enumerate([('2+ concurrent',2),('3+ concurrent',3),('4+ concurrent',4)]):
        if cols[i%2].button(lab('concurrency',val,txt),use_container_width=True,key=f'qx{i}'):
            st.session_state.qsel['concurrency']=[] if val in st.session_state.qsel['concurrency'] else [val]; st.rerun()

    nsel=sum(len(v) for v in st.session_state.qsel.values())
    go=st.button(f'CALCULATE SELECTED ({nsel})',type='primary',use_container_width=True,disabled=nsel==0)
    if st.button('Clear selections',use_container_width=True):
        for k in st.session_state.qsel: st.session_state.qsel[k]=[]
        st.session_state.pop('qresult',None); st.rerun()
    if go:
        s=st.session_state.qsel; dfq=enriched if s['concurrency'] else clean; source='Concurrency-enriched normalized records' if s['concurrency'] else 'Clean normalized table'; ev=[]; co=[]
        if s['clinical']: ev.append(f('impression_family','in',s['clinical'],'Clinical family selection'))
        labels={'turnout_le_2m':'Turnout ≤ 2 min','response_le_10m':'Response ≤ 10 min','scene_le_20m':'Scene ≤ 20 min','commitment_gt_90m':'Commitment > 90 min'}
        for fld in s['performance']: ev.append(f(fld,'==',True,labels[fld]))
        if s['concurrency']:
            nn=s['concurrency'][0]; fld={2:'concurrent_2plus_at_start',3:'concurrent_3plus_at_start',4:'concurrent_4plus_at_start'}[nn]; ev.append(f(fld,'==',True,f'At least {nn} incidents active at dispatch'))
        if s['gender']: co.append(f('gender_norm','in',s['gender'],'Gender selection'))
        if s['weekday']:
            dd=[]; dd+=['Saturday','Sunday'] if 'Weekend' in s['weekday'] else []; dd += [x for x in s['weekday'] if x!='Weekend']; co.append(f('weekday','in',list(dict.fromkeys(dd)),'Selected day(s)'))
        if s['season']:
            mm={'Winter':[12,1,2],'Spring':[3,4,5],'Summer':[6,7,8],'Fall':[9,10,11]}; months=[]
            for ss in s['season']: months+=mm[ss]
            co.append(f('month','in',list(dict.fromkeys(months)),'Selected season(s)'))
        if s['time']:
            hh=[]
            for lo,hi in s['time']: hh+=list(range(lo,hi))
            co.append(f('hour','in',list(dict.fromkeys(hh)),'Selected 4-hour block(s)'))
        if s['age']:
            aa=[]
            for lo,hi in s['age']: aa+=list(range(lo,hi+1))
            co.append(f('age','in',list(dict.fromkeys(aa)),'Selected age category/categories'))
        if not ev and co: ev=[co.pop(0)]
        st.session_state.qresult=(dfq,ev,co,source)
    if 'qresult' in st.session_state:
        render_result(*st.session_state.qresult,'quick')

# BUILD
with tabs[1]:
    st.subheader('Build a Probability')
    mode=st.radio('Event type',['Clinical impression','Dispatch complaint','Concurrency','Performance'],horizontal=True)
    df=clean; source='Clean normalized table'; ev=[]
    if mode=='Clinical impression':
        v=st.selectbox('What happened?',['All']+uniques(clean,'impression_family')); ev=[] if v=='All' else [f('impression_family','==',v,f'Provider impression = {v}')]
    elif mode=='Dispatch complaint':
        v=st.selectbox('What was dispatched?',['All']+uniques(clean,'dispatch_family')); ev=[] if v=='All' else [f('dispatch_family','==',v,f'Dispatch family = {v}')]
    elif mode=='Concurrency':
        df=enriched; source='Concurrency-enriched normalized records'; nn=st.radio('Concurrent threshold',[2,3,4],horizontal=True); fld={2:'concurrent_2plus_at_start',3:'concurrent_3plus_at_start',4:'concurrent_4plus_at_start'}[nn]; ev=[f(fld,'==',True,f'At least {nn} incidents active at dispatch')]
    else:
        txt=st.selectbox('Performance event',['Turnout ≤ 2 min','Response ≤ 10 min','Response ≤ 15 min','Scene ≤ 20 min','Scene ≤ 30 min','Commitment > 90 min']); mp={'Turnout ≤ 2 min':'turnout_le_2m','Response ≤ 10 min':'response_le_10m','Response ≤ 15 min':'response_le_15m','Scene ≤ 20 min':'scene_le_20m','Scene ≤ 30 min':'scene_le_30m','Commitment > 90 min':'commitment_gt_90m'}; ev=[f(mp[txt],'==',True,txt)]
    st.markdown('#### GIVEN'); c1,c2,c3=st.columns(3); month=c1.selectbox('Month',['Any']+[MONTH_LABELS[i] for i in range(1,13)]); gender=c2.selectbox('Gender',['Any']+uniques(clean,'gender_norm')); day=c3.selectbox('Day type',['Any','Weekday','Weekend']); co=[]
    if month!='Any': m=next(k for k,v in MONTH_LABELS.items() if v==month); co.append(f('month','==',m,f'Month = {month}'))
    if gender!='Any': co.append(f('gender_norm','==',gender,f'Gender = {gender}'))
    if day=='Weekend': co.append(f('is_weekend','==',True,'Weekend'))
    elif day=='Weekday': co.append(f('is_weekend','==',False,'Weekday'))
    c4,c5,c6=st.columns(3); am=c4.selectbox('Age',['Any','Under','Over','Range']); a1=a2=None
    if am=='Under': a1=c4.number_input('Age <',0,120,10)
    elif am=='Over': a1=c4.number_input('Age >',0,120,50)
    elif am=='Range': a1=c4.number_input('Age ≥',0,120,18); a2=c4.number_input('Age ≤',0,120,64)
    zone=c5.selectbox('Zone',['Any']+uniques(clean,'zone_norm')); unit=c6.selectbox('Unit',['Any']+uniques(clean,'unit_norm'))
    if am=='Under': co.append(f('age','<',a1,f'Age < {a1}'))
    elif am=='Over': co.append(f('age','>',a1,f'Age > {a1}'))
    elif am=='Range': co += [f('age','>=',a1,f'Age ≥ {a1}'),f('age','<=',a2,f'Age ≤ {a2}')]
    if zone!='Any': co.append(f('zone_norm','==',zone,f'Zone = {zone}'))
    if unit!='Any': co.append(f('unit_norm','==',unit,f'Unit = {unit}'))
    if st.button('CALCULATE PROBABILITY',type='primary',use_container_width=True,key='buildgo'): st.session_state.build=(df,ev,co,source)
    if 'build' in st.session_state: render_result(*st.session_state.build,'build')

# BOOLEAN BUILDER
with tabs[2]:
    st.subheader('Boolean Query Builder'); st.caption('Explicit AND / OR / NOT logic. Event filters form the numerator criterion; conditions define the denominator population.')
    ds=st.radio('Dataset',['Normalized records','Concurrency-enriched records'],horizontal=True); dfb=enriched if ds.startswith('Concurrency') else clean
    fieldmap={'Clinical impression':'impression_family','Dispatch family':'dispatch_family','Gender':'gender_norm','Weekday':'weekday','Month':'month','Hour':'hour','Age':'age','Zone':'zone_norm','Unit':'unit_norm','2+ concurrent':'concurrent_2plus_at_start','3+ concurrent':'concurrent_3plus_at_start','Turnout ≤2':'turnout_le_2m','Response ≤10':'response_le_10m'}
    def filter_rows(prefix,n):
        out=[]
        for i in range(n):
            st.markdown(f'**Filter {i+1}**')
            name=st.selectbox(f'Field {i+1}',list(fieldmap),key=f'{prefix}f{i}')
            fld=fieldmap[name]
            c_op,c_not=st.columns([2,1])
            neg=c_not.checkbox('NOT',key=f'{prefix}n{i}')
            if fld in ('age','hour','month'):
                op=c_op.selectbox('Operator',['==','<','<=','>','>='],key=f'{prefix}o{i}')
                val=st.number_input('Value',0,200,0,key=f'{prefix}v{i}')
            elif fld in ('concurrent_2plus_at_start','concurrent_3plus_at_start','turnout_le_2m','response_le_10m'):
                op='=='
                c_op.caption('Operator: == True')
                val=True
            else:
                op='=='
                c_op.caption('Operator: ==')
                val=st.selectbox('Value',uniques(dfb,fld),key=f'{prefix}v{i}')
            out.append(f(fld,'!=' if neg else op,val,('NOT ' if neg else '')+f'{name} {op} {val}'))
            if i < n-1: st.divider()
        return out
    st.markdown('#### Event group'); elogic=st.radio('Event logic',['AND','OR'],horizontal=True,key='elogic'); en=int(st.number_input('Number of event filters',1,4,1)); ef=filter_rows('e',en)
    st.markdown('#### Condition group'); clogic=st.radio('Condition logic',['AND','OR'],horizontal=True,key='clogic'); cn=int(st.number_input('Number of condition filters',0,6,1)); cf=filter_rows('c',cn)
    if st.button('RUN BOOLEAN QUERY',type='primary',use_container_width=True,key='boolgo'):
        st.session_state.boolres=(calc_boolean(dfb,[{'logic':elogic,'filters':ef}],[{'logic':clogic,'filters':cf}]),ef,cf,elogic,clogic,ds)
    if 'boolres' in st.session_state:
        r,ef,cf,el,cl,ds=st.session_state.boolres; lo,hi=wilson(r['numerator'],r['denominator']); c1,c2,c3,c4=st.columns(4); c1.metric('Probability','—' if r['probability'] is None else f"{r['probability']*100:.2f}%"); c2.metric('Numerator',f"{r['numerator']:,}"); c3.metric('Denominator',f"{r['denominator']:,}"); c4.metric('95% Wilson CI','—' if lo is None else f'{lo*100:.1f}–{hi*100:.1f}%')
        with st.expander('Boolean logic / audit',expanded=True):
            st.write('**Event logic:**', el)
            valid_event = [x for x in (ef or []) if isinstance(x,dict) and x.get('label')]
            if valid_event:
                for x in valid_event:
                    st.markdown(f"- {x['label']}")
            else:
                st.markdown("- All records")

            st.write('**Condition logic:**', cl)
            valid_condition = [x for x in (cf or []) if isinstance(x,dict) and x.get('label')]
            if valid_condition:
                for x in valid_condition:
                    st.markdown(f"- {x['label']}")
            else:
                st.markdown("- All records")

            st.code(
                f"P = {r['numerator']} / {r['denominator']} = {r['probability']:.6f}"
                if r['denominator'] else 'Undefined: denominator = 0'
            )

# COMPARE
with tabs[3]:
    st.subheader('Compare two groups'); event=st.selectbox('Event',uniques(clean,'impression_family'),key='cmpevent'); ev=[f('impression_family','==',event,f'Provider impression = {event}')]
    def group(prefix):
        m=st.selectbox('Month',['Any']+[MONTH_LABELS[i] for i in range(1,13)],key=prefix+'m')
        a=st.selectbox('Age',['Any','Under 10','0–17','Over 50','65+','85+'],key=prefix+'a')
        g=st.selectbox('Gender',['Any']+uniques(clean,'gender_norm'),key=prefix+'g')
        out=[]
        if m!='Any': mm=next(k for k,v in MONTH_LABELS.items() if v==m); out.append(f('month','==',mm,f'Month = {m}'))
        if a=='Under 10': out.append(f('age','<',10,'Age < 10'))
        elif a=='0–17': out += [f('age','>=',0,'Age ≥ 0'),f('age','<=',17,'Age ≤ 17')]
        elif a=='Over 50': out.append(f('age','>',50,'Age > 50'))
        elif a=='65+': out.append(f('age','>=',65,'Age ≥ 65'))
        elif a=='85+': out.append(f('age','>=',85,'Age ≥ 85'))
        if g!='Any': out.append(f('gender_norm','==',g,f'Gender = {g}'))
        return out
    st.markdown('**Group A**'); ga=group('A'); st.markdown('**Group B**'); gb=group('B')
    if st.button('COMPARE GROUPS',type='primary',use_container_width=True,key='cmpgo'):
        A=calc(clean,ev,ga); B=calc(clean,ev,gb); st.session_state.cmp=(A,B,two_proportion_stats(A['numerator'],A['denominator'],B['numerator'],B['denominator']),ga,gb,event)
    if 'cmp' in st.session_state:
        A,B,s,ga,gb,event=st.session_state.cmp; ca,cb=st.columns(2)
        with ca:
            st.metric('Group A','—' if A['probability'] is None else f"{A['probability']*100:.2f}%"); st.markdown(f"**{A['numerator']:,} event records / {A['denominator']:,} total qualifying records**"); la,ha=wilson(A['numerator'],A['denominator']); st.caption('95% CI: —' if la is None else f'95% CI: {la*100:.1f}–{ha*100:.1f}%')
        with cb:
            st.metric('Group B','—' if B['probability'] is None else f"{B['probability']*100:.2f}%"); st.markdown(f"**{B['numerator']:,} event records / {B['denominator']:,} total qualifying records**"); lb,hb=wilson(B['numerator'],B['denominator']); st.caption('95% CI: —' if lb is None else f'95% CI: {lb*100:.1f}–{hb*100:.1f}%')
        if s:
            x,y,z=st.columns(3); x.metric('Difference',f"{s['difference']*100:+.2f} pp"); y.metric('Risk ratio','—' if s['risk_ratio'] is None else f"{s['risk_ratio']:.2f}×"); z.metric('Odds ratio','—' if s['odds_ratio'] is None else f"{s['odds_ratio']:.2f}"); st.write(f"95% CI for difference: {s['difference_ci_low']*100:+.2f} to {s['difference_ci_high']*100:+.2f} percentage points.")
            lines=[f"Group A: {A['numerator']}/{A['denominator']} = {A['probability']*100:.2f}%",f"Group B: {B['numerator']}/{B['denominator']} = {B['probability']*100:.2f}%",f"Difference: {s['difference']*100:+.2f} pp",f"Risk ratio: {s['risk_ratio']:.2f}x" if s['risk_ratio'] else 'Risk ratio: —',f"Odds ratio: {s['odds_ratio']:.2f}" if s['odds_ratio'] else 'Odds ratio: —']
            st.download_button('Download comparison PDF',pdf_bytes('EMS Probability Comparison',f'P({event} | Group A) vs P({event} | Group B)',A,[f'Provider impression = {event}'],[x['label'] for x in ga],'Clean normalized table',lines),file_name='ems_probability_comparison.pdf',mime='application/pdf',key='cmppdf')

# TEMPORAL TRENDS
with tabs[4]:
    st.subheader('Temporal Trends'); event=st.selectbox('Clinical event',uniques(clean,'impression_family'),key='trendevent'); dim=st.selectbox('Trend dimension',['Year','Month','Weekday','Hour','4-hour block']); ev=[f('impression_family','==',event,f'Provider impression = {event}')]; rows=[]
    if dim=='Year':
        for v in sorted(int(x) for x in pd.to_numeric(clean['year'],errors='coerce').dropna().unique()):
            r=calc(clean,ev,[f('year','==',v,f'Year = {v}')]); rows.append({'label':str(v),'probability':r['probability']*100 if r['probability'] is not None else None,'n':r['denominator']})
    elif dim=='Month':
        for v in range(1,13):
            r=calc(clean,ev,[f('month','==',v,f'Month = {MONTH_LABELS[v]}')]); rows.append({'label':MONTH_LABELS[v][:3],'probability':r['probability']*100 if r['probability'] is not None else None,'n':r['denominator']})
    elif dim=='Weekday':
        for v in ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']:
            r=calc(clean,ev,[f('weekday','==',v,f'Weekday = {v}')]); rows.append({'label':v[:3],'probability':r['probability']*100 if r['probability'] is not None else None,'n':r['denominator']})
    elif dim=='Hour':
        for v in range(24):
            r=calc(clean,ev,[f('hour','==',v,f'Hour = {v}')]); rows.append({'label':f'{v:02d}','probability':r['probability']*100 if r['probability'] is not None else None,'n':r['denominator']})
    else:
        for txt,hours in [('00–04',range(0,4)),('04–08',range(4,8)),('08–12',range(8,12)),('12–16',range(12,16)),('16–20',range(16,20)),('20–24',range(20,24))]:
            r=calc(clean,ev,[f('hour','in',list(hours),txt)]); rows.append({'label':txt,'probability':r['probability']*100 if r['probability'] is not None else None,'n':r['denominator']})
    tdf=pd.DataFrame(rows); chart=alt.Chart(tdf).mark_line(point=True).encode(x=alt.X('label:N',title=dim),y=alt.Y('probability:Q',title='Observed probability (%)'),tooltip=[alt.Tooltip('label:N',title=dim),alt.Tooltip('probability:Q',format='.2f'),alt.Tooltip('n:Q',title='Denominator')]).properties(height=310); st.altair_chart(chart,use_container_width=True); st.dataframe(tdf,use_container_width=True,hide_index=True)

# CONCURRENCY
with tabs[5]:
    st.subheader('Concurrency'); nn=st.radio('Threshold',[2,3,4],horizontal=True); fld={2:'concurrent_2plus_at_start',3:'concurrent_3plus_at_start',4:'concurrent_4plus_at_start'}[nn]; ev=[f(fld,'==',True,f'At least {nn} incidents active at dispatch')]; render_result(conc,ev,[],'Incident-level concurrency table','conc')
    rows=[]
    for m in range(1,13):
        r=calc(conc,ev,[f('month','==',m,f'Month = {MONTH_LABELS[m]}')]); rows.append({'month':MONTH_LABELS[m][:3],'probability':r['probability']*100 if r['probability'] is not None else None,'n':r['denominator']})
    cdf=pd.DataFrame(rows); st.altair_chart(alt.Chart(cdf).mark_bar().encode(x=alt.X('month:N',sort=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']),y=alt.Y('probability:Q',title='Probability (%)'),tooltip=['month',alt.Tooltip('probability:Q',format='.2f'),'n']).properties(height=290),use_container_width=True)

with tabs[6]:
    st.subheader('Methods / Audit')

    st.markdown('''
### Concise User Guide

**Quick Buttons**  
Select one or more filters, then choose **Calculate Selected**. Selections within the same category are treated as OR; selections across different categories are treated as AND.

**Build a Probability**  
Choose the event first, then add GIVEN conditions such as month, age, gender, day type, zone, or unit. Selecting **All** under Clinical impression applies no clinical-impression restriction.

**Boolean Builder**  
Use this for explicit AND / OR / NOT logic. Build the event group and conditioning group separately, then run the query.

**Compare**  
Define Group A and Group B for the same clinical event. Read the result as numerator / denominator, probability, 95% CI, percentage-point difference, risk ratio, and odds ratio.

**Temporal Trends**  
Choose a clinical event and view its observed probability by year, month, weekday, hour, or 4-hour block.

**Concurrency**  
Use this tab for pure incident-level system-demand probabilities such as 2+, 3+, or 4+ simultaneous incidents.

**Mobile use**  
The sidebar starts collapsed on phones. Swipe/scroll the tab row horizontally to reach all sections. Controls are sized for touch, and charts resize to the screen width.

**Exports**  
Use JSON for machine-readable audit records and PDF for concise executive briefs.
''')

    st.markdown('''
### Methods

**Dataset conventions**
- Routine clinical and demographic probabilities use the cleaned normalized record table.
- Pure concurrency probabilities use the one-row-per-incident concurrency table.
- Combined clinical + concurrency queries use the concurrency-enriched normalized table.

**Concurrency**
Incident start = earliest unit-notified timestamp; incident end = latest back-in-service timestamp. A concurrent arrival occurs when a new incident begins while another distinct incident remains active.

**Confidence intervals**
Single proportions use Wilson score intervals. Compare mode reports Wilson intervals for each group plus a 95% interval for the absolute difference in proportions.

**Interpretation**
Observed historical probabilities are descriptive; they do not imply causation or guarantee future demand.
''')

    st.markdown('''
### Version Notes

**v3.1.0**
- Mobile-first responsive layout and collapsed sidebar.
- Touch-sized buttons and two-across Quick Button grids.
- Horizontally scrollable tab navigation on narrow screens.
- Reworked Boolean Builder and Compare inputs for phone use.
- Mobile-friendly result metrics and stacked export actions.

**v3.0.3**
- Fixed Boolean audit NULL rendering and retained the in-app User Guide / Version Notes.

**v3.0**
- Added Boolean Query Builder with AND / OR / NOT logic.
- Added Temporal Trends by year, month, weekday, hour, and 4-hour block.
- Expanded Compare with explicit numerator / denominator, Wilson CI for each group, percentage-point difference, risk ratio, odds ratio, and CI for the difference.
- Added one-click PDF executive brief export.
- Added dedicated Concurrency tab.

**v2.8.x**
- Added enriched concurrency for combined clinical and demographic queries.
- Added multi-select Quick Buttons.
- Added 8 clinical quick-access families.
- Added gender, age, weekday, season, and time-of-day filters.
- Added **All** as a Clinical impression choice.
- Added chief-level Wilson CI explanation.
- Clarified Compare numerator / denominator display.
- Added department branding and A-Shift Data Performance footer.
''')

    st.code('A-Shift Data Performance | Insights for Action')

st.divider(); st.caption('A-Shift Data Performance | Insights for Action')
