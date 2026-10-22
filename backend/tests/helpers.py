"""测试辅助：从字节码层面断言代码结构。

为什么不直接 inspect.getsource 做文本匹配：
  - 源码里的注释和 docstring 同样包含关键词，按文本匹配会误报；
  - Python 3.11 下推导式是独立的代码对象，外层函数的 co_names 看不到里面的属性访问。
co_names 只记录真正被访问的属性/全局名，绕开注释，递归展开又能覆盖推导式。
"""
import types


def _walk_code(func):
    """产出函数及其所有嵌套代码对象（推导式、内层函数等）。"""
    stack = [func.__code__]
    while stack:
        code = stack.pop()
        yield code
        for const in code.co_consts:
            if isinstance(const, types.CodeType):
                stack.append(const)


def accessed_names(func) -> set[str]:
    """收集函数（含嵌套代码对象）里访问过的所有属性名与全局名。"""
    names: set[str] = set()
    for code in _walk_code(func):
        names.update(code.co_names)
    return names


def string_consts(func) -> set[str]:
    """收集函数（含嵌套代码对象）里出现的所有字符串常量。

    字典键、状态字面量这类值不会进 co_names（那是留给属性/全局名的），
    只能从 co_consts 里取 —— 断言「有没有清空某个字段」就得靠它。

    注意 Python 3.11 会用 BUILD_CONST_KEY_MAP 把字典的常量键打包成一个元组常量，
    而不是逐个字符串入池，所以必须递归展开元组，否则「写了这个 key」也查不出来。
    """
    consts: set[str] = set()
    for code in _walk_code(func):
        for value in code.co_consts:
            _collect_strings(value, consts)
    return consts


def _collect_strings(value, out: set[str]) -> None:
    if isinstance(value, str):
        out.add(value)
    elif isinstance(value, tuple):
        for item in value:
            _collect_strings(item, out)
