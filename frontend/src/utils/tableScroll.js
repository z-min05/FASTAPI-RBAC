/**
 * 表格统一滚动配置：所有列表都同时带纵向与横向滚动条，且长文本列按声明宽度截断。
 *
 * 关于 x（关键）：
 *   必须给「确定长度」——即列宽之和，不能用 'max-content'，也不能给 'auto'。
 *   实测（Chromium）：x 为 'max-content' 或 'auto' 时，表格宽度是"非确定值"，
 *   固定布局下列宽会被抬到「声明宽度与内容宽度的较大值」，长文本会把列撑开，
 *   ellipsis 截断完全失效（例：声明 320px 的标题列被 32 字标题撑到 480px）。
 *   只有确定长度的表格宽度，才能让列上声明的 width 成为硬约束。
 *
 *   组件内部会补 min-width: 100%，所以列宽之和小于容器时，列会等比拉伸、
 *   右侧不留白；大于容器时出现横向滚动条，列宽严格等于声明值。
 *
 * y：表体最大高度，表头吸顶；组件对表体固定设置 overflow-y: scroll，
 *   因此纵向滚动条始终可见。
 */

const SCROLL_Y = {
  normal: 'calc(100vh - 340px)',
  tall: 'calc(100vh - 420px)',
  modal: 420
}

/** 累加列声明宽度（支持分组表头），作为表格的固定总宽 */
export function sumColumnsWidth(columns) {
  let total = 0
  for (const col of columns || []) {
    if (!col) continue
    if (col.children && col.children.length) {
      total += sumColumnsWidth(col.children)
    } else if (typeof col.width === 'number') {
      total += col.width
    }
  }
  return total
}

function makeScroll(columns, kind) {
  return { x: sumColumnsWidth(columns), y: SCROLL_Y[kind] }
}

/** 标准列表页表格（页头 + 筛选 + 分页 + 布局留白约占 340px） */
export const TABLE_SCROLL = (columns) => makeScroll(columns, 'normal')

/** 筛选/操作区更高的列表页表格（如用例管理、计划详情） */
export const TABLE_SCROLL_TALL = (columns) => makeScroll(columns, 'tall')

/** 弹窗、抽屉内的表格：用固定高度，避免按视口取高时溢出弹窗 */
export const TABLE_SCROLL_MODAL = (columns) => makeScroll(columns, 'modal')
