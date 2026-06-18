/**
 * Konva 按需入口：只引入项目用到的图形，缩小打包体积。
 *
 * 运行时从 konva/lib/Core 取核心（Stage/Layer/Group/Shape/Animation/Easings…），
 * 再具名引入用到的图形并挂回 Konva 完成注册。
 * 类型上 cast 成完整 konva 的默认导出（`import('konva')` 仅类型、构建期擦除，
 * 不会把整包打进产物），让 `Konva.Stage` / `new Konva.Circle()` 都有类型。
 *
 * 全项目统一从 '@/lib/konva' 导入，避免漏注册某个图形。
 * 当前用到：Rect / Circle / Line / Text / Arrow。
 */
import KonvaCore from 'konva/lib/Core';
import { Rect } from 'konva/lib/shapes/Rect';
import { Circle } from 'konva/lib/shapes/Circle';
import { Line } from 'konva/lib/shapes/Line';
import { Text } from 'konva/lib/shapes/Text';
import { Arrow } from 'konva/lib/shapes/Arrow';

Object.assign(KonvaCore, { Rect, Circle, Line, Text, Arrow });

const Konva = KonvaCore as unknown as typeof import('konva').default;
export default Konva;

// 类型转发（仅类型、构建期擦除）：供类型标注使用，替代 `Konva.Stage` 命名空间写法
export type { Stage } from 'konva/lib/Stage';
export type { Layer } from 'konva/lib/Layer';
export type { Group } from 'konva/lib/Group';
export type { Animation } from 'konva/lib/Animation';
