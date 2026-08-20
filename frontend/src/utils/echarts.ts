/* ============================================================
   ECHARTS 按需注册 —— 只打包用到的图表与组件，显著缩减体积
   图表：折线（趋势）/ 柱状（词频）/ 饼图（来源分布）
   ============================================================ */

import { use } from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
])
