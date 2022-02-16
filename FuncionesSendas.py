import datetime as dt
import holidays_co
import pandas as pd
import numpy as np
from scipy.stats import norm
import plotly.graph_objs as go


def diashab(ini,fin):

    """Para un rango de fechas, me devuelve los días hábiles de Colombia, date1 la fecha inicial y date 2 la fecha final"""
    holidays=pd.DataFrame(columns=['date','celebration'])
    for i in range(ini.year,fin.year+1):
        holidays=holidays.append(pd.DataFrame(holidays_co.get_colombia_holidays_by_year(i)))
    dias = pd.DataFrame([ini + dt.timedelta(days=d) for d in range((fin - ini).days + 1)],columns=['date'])
    dias['Weekday']=dias['date'].apply(lambda x:x.weekday())
    dias=dias[dias['Weekday'].isin([0,1,2,3,4])]
    dias=dias[~dias['date'].isin(holidays['date'])]
    return dias.drop('Weekday',axis=1)

def calcEURUSD(df):
    pvt=pd.pivot_table(df,index='Fecha',columns='Factor',values='Valor')
    pvt=pvt.dropna(axis=0)
    pvt['EURUSD']=pvt['EURCOP']/pvt['TRM']
    return pd.melt(pvt.reset_index(),id_vars='Fecha',value_name='Valor',var_name='Factor')

def montecarlo(vi,m,s,t,perc):
    """Devuelve observación del percentil definido de una simulación montecarlo
    con un valor inicial (vi), media (m), desviación estándar (s) y tiempo (t)"""
    vf=vi*np.exp((m-(s**2)/2)*t+s*norm.ppf(perc)*(t**0.5))
    return vf

def simul(Fecha,anos):
    Factores=['TRM','EURCOP']
    df=pd.read_csv(r'\\epm-file02\DATALAKE\ModeloValorRiesgo\ProveedorPrecios\Hist_FR.csv',index_col=0)
    

    # Factor EURCOP faltante
    moneEUR=pd.read_csv(r'\\epm-file02\DATALAKE\ModeloSendasCambiarias\Moneda.csv',parse_dates=['Fecha'])
    moneEUR['Fecha']=moneEUR['Fecha'].apply(lambda x:int(x.strftime('%Y%m%d')))
    moneEUR=moneEUR.rename(columns={'Moneda':'Factor'})
    moneEUR['Factor']='EURCOP'
    moneEUR=moneEUR.rename(columns={' Valor':'Valor'})
    df=pd.concat([df,moneEUR],ignore_index=True)

    #Continua
    df=df[df['Factor'].isin(Factores)].drop('Nodo',axis=1).reset_index(drop=True)
    # df=calcEURUSD(df)

    Hist=pd.read_excel(r'\\epm-file02\DATALAKE\ModeloSendasCambiarias\HistoriaHasta20180831.xlsx',parse_dates=['Fecha'])
    Hist['Fecha']=Hist['Fecha'].apply(lambda x:int(x.strftime('%Y%m%d')))
    Hist=pd.melt(Hist,id_vars='Fecha',var_name='Factor',value_name='Valor')
    df=pd.concat([df,Hist]).sort_values(by=['Factor','Fecha']).reset_index(drop=True)
    # df.to_csv(r'\\epm-file02\DATALAKE\ModeloSendasCambiarias\Hist_Cons.csv')
    
    # EWMA=pd.read_csv(r'\\epm-file02\DATALAKE\ModeloValorRiesgo\ProveedorPrecios\EWMA.csv',index_col=0,dtype={'Fecha':int})
    # EWMA=EWMA[EWMA['Factor'].isin(Factores)].reset_index()
    EWMA=EWMAf(df,0.94)
    dias=diashab(Fecha+dt.timedelta(days=1),Fecha+dt.timedelta(days=365*anos+1)).reset_index(drop=True)['date']
    Fecha_int=int(Fecha.strftime('%Y%m%d'))

    Percentiles=[0.05,0.25,0.5,0.75,0.95]
    
    columnas=['Fecha','Factor','Percentil','Valor']
    resT=pd.DataFrame(columns=columnas)
    for i in df['Factor'].unique():
        def_i=df[df['Factor']==i]
        EWMA_i=EWMA[(EWMA['Factor']==i)&(EWMA['Fecha']<=Fecha_int)]
        EWMA_i=EWMA_i.iloc[-1,-1]/(252**0.5)
 
        df_i=df[(df['Factor']==i)&(df['Fecha']<=Fecha_int)]
        df_i.loc[:,'Valor'].pct_change()
        ret_i=df_i.loc[:,'Valor'].pct_change().mean()
        val_fin=df_i.iloc[-1,1]
        for q in Percentiles:
            res=pd.DataFrame([[dias[u],i,q,montecarlo(val_fin,ret_i,EWMA_i,u+1,q)] for u in range(len(dias))],columns=columnas)
            resT=pd.concat([resT,res],ignore_index=True)
    for i in resT['Factor'].unique():

        res_pvt=pd.pivot_table(resT[resT['Factor']==i],index='Fecha',columns='Percentil',values='Valor')
        res_pvt.to_excel(r'\\epm-file02\DATALAKE\ModeloSendasCambiarias\Resultados\{}_{}_ModeloSendas.xlsx'.format(Fecha.strftime('%Y%m%d'),i))
    
    df.to_csv(r'\\epm-file02\DATALAKE\ModeloSendasCambiarias\Hist_Cons.csv')
    resT['Fecha']=resT['Fecha'].apply
    return df

def grafica(Fecha,factor):
    df=pd.read_excel(r'\\epm-file02\DATALAKE\ModeloSendasCambiarias\Resultados\{}_{}_ModeloSendas.xlsx'.format(Fecha.strftime('%Y%m%d'),factor))
    fig=go.Figure()
    for i in df.columns[1:]:
        fig.add_traces(
            go.Scatter(
                x=df['Fecha'],
                y=df[i],
                name='Percentil {}'.format(i)
            )
        )
    fig.update_layout(title_text="Senda tasa {}, Corte: {}".format(factor,Fecha))
    return fig

def EWMAf(df,lamb):
    """Devuelve volatilidad EWMA  tomando las fechas de inicio y de final
    definidas como argumentos y los valores diarios de los factores de riesgo"""
    df=pd.pivot_table(df,index='Fecha',columns='Factor',values='Valor').pct_change()
    # return df
    res=pd.DataFrame(columns=df.columns)
    for j in df.columns:
        df_f=pd.DataFrame(df.loc[:,j])
        ewma=[]
        for i in df_f.index:
            if i==df_f.index[0]:
                ewma.append(0)
            else:
                ewma.append(np.power((1-lamb)*np.power(df_f.loc[i,j],2)+lamb*np.power(ewma[-1],2),0.5))
        df_f['EWMA']=[i*np.sqrt(252) for i in ewma]
        res[j]=df_f['EWMA']
        res=res.rename(columns={'EWMA':j})
    res=res.reset_index()
    # res['Fecha']=res['Fecha'].apply(lambda x:x.strftime("%Y%m%d"))
    res.set_index('Fecha',inplace=True)
    return pd.melt(res,ignore_index=False).reset_index()