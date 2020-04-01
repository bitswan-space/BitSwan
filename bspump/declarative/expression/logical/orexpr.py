import functools

from ..abc import Expression
from ..builder import ExpressionBuilder


class OR(Expression):

	def __init__(self, expression: dict):
		super().__init__(expression)
		self.Items = []
		for item in expression.get("items", []):
			self.Items.append(ExpressionBuilder.build(item))

	def __call__(self, context, event, *args, **kwargs):
		return functools.reduce(
			lambda x, y: x(context, event, *args, **kwargs) or y(context, event, *args, **kwargs) if isinstance(x, Expression) else x or y(context, event, *args, **kwargs),
			self.Items
		)
