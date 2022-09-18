import datetime as dt
import holidays_co
import pandas as pd
import numpy as np
import investpy
from scipy.stats import norm
import plotly.graph_objs as go
import os
import json

with open("rutas.json") as file:
    dic_path=json.load(file)

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

def montecarlo(vi,m,s,t,perc):
    """Devuelve observación del percentil definido de una simulación montecarlo
    con un valor inicial (vi), media (m), desviación estándar (s) y tiempo (t)"""
    vf=vi*np.exp((m-(s**2)/2)*t+s*norm.ppf(perc)*(t**0.5))
    return vf

def simul(Fecha,anos,moneda):
    """Simula tasa de cambio para una fecha, con x años de periodo de tiempo y
    con la moneda definida"""    
    Fecha_ini=dt.date(2015,1,1)

    df=investpy.get_currency_cross_historical_data(moneda,from_date=Fecha_ini.strftime('%d/%m/%Y'),to_date=Fecha.strftime('%d/%m/%Y')).reset_index()        

    df['Date']=df['Date'].apply(lambda x:int(x.strftime("%Y%m%d")))

    nombres={'COP':'USDCOP','GTQ':'USDGTQ','MXN':'USDMXN','CLP':'USDCLP','USD':'EURUSD'}
    df['Currency']=df['Currency'].map(nombres)

    EWMA=EWMAf(df,0.94)
    dias=diashab(Fecha+dt.timedelta(days=1),Fecha+dt.timedelta(days=365*anos+1)).reset_index(drop=True)['date']
    Fecha_int=int(Fecha.strftime('%Y%m%d'))

    Percentiles=[0.05,0.25,0.5,0.75,0.95]
    
    columnas=['Date','Currency','Percentil','Close']
    resT=pd.DataFrame(columns=columnas)
    for i in df['Currency'].unique():
        def_i=df[df['Currency']==i]
        EWMA_i=EWMA[(EWMA['Currency']==i)&(EWMA['Date']<=Fecha_int)]
        EWMA_i=EWMA_i.iloc[-1,-1]/(252**0.5)
 
        df_i=df[(df['Currency']==i)&(df['Date']<=Fecha_int)]
        df_i.loc[:,'Close'].pct_change()
        ret_i=df_i.loc[:,'Close'].pct_change().mean()
        val_fin=df_i.iloc[-1,1]
        for q in Percentiles:
            res=pd.DataFrame([[dias[u],i,q,montecarlo(val_fin,ret_i*0,EWMA_i,u+1,q)] for u in range(len(dias))],columns=columnas)
            resT=pd.concat([resT,res],ignore_index=True)
    for i in resT['Currency'].unique():

        res_pvt=pd.pivot_table(resT[resT['Currency']==i],index='Date',columns='Percentil',values='Close')
        res_pvt.to_excel(os.path.join(dic_path['Sendas'],'{}_{}_ModeloSendas.xlsx'.format(Fecha.strftime('%Y%m%d'),i)))
    
    resT['Date']=resT['Date'].apply
    return df

def grafica(Fecha,factor):
    df=pd.read_excel(os.path.join(dic_path['Sendas'],'{}_{}_ModeloSendas.xlsx'.format(Fecha.strftime('%Y%m%d'),factor)))
    hist=pd.read_csv(os.path.join(dic_path['Sendas'],'Hist_Cons.csv'),index_col=0)
    hist['Date']=hist['Date'].apply(lambda x:dt.datetime.strptime(str(x),'%Y%m%d'))
    hist=hist[hist['Currency']==factor]
    fig=go.Figure()
    for i in df.columns[1:]:
        fig.add_traces(
            go.Scatter(
                x=df['Date'],
                y=df[i],
                name='Percentil {}'.format(i)
            )
        )
    fig.add_traces(
        go.Scatter(
            x=hist['Date'],
            y=hist['Close'],
            name='Histórico'
        )
    )
    fig.update_layout(title_text="Senda tasa {}, Corte: {}".format(factor,Fecha))
    return fig


def EWMAf(df,lamb):
    """Devuelve volatilidad EWMA  tomando las fechas de inicio y de final
    definidas como argumentos y los valores diarios de los factores de riesgo"""
    df=pd.pivot_table(df,index='Date',columns='Currency',values='Close').pct_change()
    # return df
    res=pd.DataFrame(columns=df.columns)
    for j in df.columns:
        df_f=pd.DataFrame(df.loc[:,j])
        ewma=[]
        for i in df_f.index:
            if i==df_f.index[0]:
                ewma.append(0)
            else:
                if pd.isnull(df_f.loc[i,j])==True:
                    ewma.append(0)
                else:
                    ewma.append(np.power((1-lamb)*np.power(df_f.loc[i,j],2)+lamb*np.power(ewma[-1],2),0.5))

                # ewma.append(np.power((1-lamb)*np.power(df_f.loc[i,j],2)+lamb*np.power(ewma[-1],2),0.5))
        df_f['EWMA']=[i*np.sqrt(252) for i in ewma]
        res[j]=df_f['EWMA']
        res=res.rename(columns={'EWMA':j})
    res=res.reset_index()
    # res['Fecha']=res['Fecha'].apply(lambda x:x.strftime("%Y%m%d"))
    res.set_index('Date',inplace=True)
    return pd.melt(res,ignore_index=False).reset_index()