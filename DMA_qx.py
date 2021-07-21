from datetime import datetime
from os import close
from vnpy.app.cta_strategy.template import CtaTemplate
from vnpy.trader.object import TickData,BarData,OrderData,TradeData
from vnpy.app.cta_strategy.base import StopOrder
from vnpy.trader.utility import BarGenerator,ArrayManager
from typing import Any, Callable

import talib

class DMA_qx(CtaTemplate):
    author = 'qx'
    
    #参数变量
    atr_multiple:int = 5
    #K线根数
    atr_par:int = 20
    #止盈
    fixed_profit_target:int = 100
    #止损
    fixed_loss_target:int = 15
    count_control:int = 1
    
    #变量
    atr_value:float = 0.0
    up_line:float = 0.0
    mid_line:float = 0.0
    down_line:float = 0.0
    pro_tar:float = 0.0
    net_stop:float = 0.0
    count_control_num:int = 0
    
    #参数和变量展示存放区
    parameters = [
        "atr_multiple",
        "atr_par",
        "fixed_profit_target",
        "fixed_loss_target",
        "count_control",
    ]
    
    variables=[
        "atr_value",
        "up_line",
        "mid_line",
        "down_line",
        "pro_tar",
        "net_stop",
        "count_control_num",
    ]
    
    def __init__(self, cta_engine: Any,strategy_name: str,vt_symbol: str,setting: dict,):
        super().__init__(cta_engine,strategy_name,vt_symbol,setting)
        
        self.bg = BarGenerator(self.on_bar,5,self.on_5min_bar)#合成器
        self.am = ArrayManager()#K线值
        self.count_control_num = 0
        self.last_bar:BarData = None
    
    def on_init(self):
        self.write_log("策略初始化")
        self.load_bar(10)#下载K线
    
    def on_start(self):
        self.write_log("策略启动")
        self.put_event()
    
    def on_stop(self):
        self.write_log("策略停止")
        self.put_event()
    
    def on_tick(self,tick:TickData):
        self.bg.update_tick(tick)
        # 在回测策略中基本上不会调用此方法
        pass
    
    def on_bar(self,bar:BarData):
        self.bg.update_bar(bar)
        # on_bar是一分钟k线
        
    def on_5min_bar(self,bar: BarData):
        self.am.update_bar(bar)#更新K线值
        if not self.am.inited:#判断K线池有没有满
            return
        # 撤单
        self.cancel_all()
        
        # if self.last_bar.datetime.hour ==14 and self.last_bar.datetime.minute== 55:
        # 如果是一分钟，就是14:59 self.last_bar要存在
        if self.last_bar and str(self.last_bar.datetime)[-14:-6]=="14:55:00":
                self.mid_line = bar.open_price
                self.atr_value = self.am.atr(self.atr_par,array=False)
                self.up_line = self.mid_line+self.atr_multiple*self.atr_value
                self.down_line = self.mid_line-self.atr_multiple*self.atr_value
                self.count_control_num = 0
                print(f"""
                      mid_line:{self.mid_line}
                      atr_value:{self.atr_value}
                      时间:{bar.datetime}
                      """)
                
        if self.pos == 0 and self.count_control_num<=self.count_control:
            if bar.close_price>self.up_line:
                self.buy(bar.close_price,1)
                # 放在这里面限制交易次数可以，但是实际中有可能并未真正执行。最好放在on_trade()里
                # self.count_control_num+=1
            if bar.close_price<self.down_line:
                self.short(bar.close_price,1)
        
        elif self.pos>0:
            # if bar.close_price>=self.down_line:
            #     pass
            if bar.close_price<self.down_line:
                self.sell(bar.close_price,abs(self.pos))
                if self.count_control_num<=self.count_control:
                    self.short(bar.close_price,1)
            if self.pro_tar:#止盈挂单
                self.sell(self.pro_tar,abs(self.pos))
            if self.net_stop:#止损挂单
                self.sell(self.net_stop,abs(self.pos),stop=True)
        elif self.pos<0:
            if bar.close_price>self.up_line:
                self.cover(bar.close_price,abs(self.pos))
                if self.count_control_num<=self.count_control:
                    self.buy(bar.close_price,1)
            if self.pro_tar:
                    self.cover(self.pro_tar,abs(self.pos))
            if self.net_stop:
                self.cover(self.net_stop,abs(self.pos))
        
        self.last_bar = bar
    
    
    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        # 一旦有成交，会调用on_trade方法，因此止盈和止损可以放在这个里面
        if self.pos >0:
        # 说明持有多单,说明刚才的交易开的是多单
            self.pro_tar = trade.price*(1000+self.fixed_profit_target)/1000
            self.net_stop = trade.price*(1000-self.fixed_loss_target)/1000
            # 当有成交后将成交次数加1
            self.count_control_num+=1 
            print(f"""
                时间:{trade.datetime}
                价格:{trade.price}
                持仓:{self.pos}
                止盈:{self.pro_tar}
                止损:{self.net_stop}
                  """)
        elif self.pos<0:
            self.pro_tar = trade.price*(1000-self.fixed_profit_target)/1000
            self.net_stop = trade.price*(1000+self.fixed_loss_target)/1000
            self.count_control_num+=1
            print(f"""
            时间:{trade.datetime}
            价格:{trade.price}
            持仓:{self.pos}
            止盈:{self.pro_tar}
            止损:{self.net_stop}
                """)
        else:
            self.pro_tar = 0
            self.net_stop = 0
            print(f"""
            时间:{trade.datetime}
            价格:{trade.price}
            持仓:{self.pos}
            止盈:{self.pro_tar}
            止损:{self.net_stop}
                """)
        self.put_event()

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        pass

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass
                
        
