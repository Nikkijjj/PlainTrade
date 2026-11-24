# adapt/
职责：把 ArgDoc 变成小白能读的东西（变换型：单次、纯函数、无状态）。
禁止：不调数据库；不知道"三个入口"存在；不做多轮讨论；import agents/pipeline/ui。
接口：每模块一个纯函数，输入输出都是 contracts/ 里的对象。