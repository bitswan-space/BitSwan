import time

import bspump
import bspump.analyzer
import bspump.unittest


class TestTimeWindowMatrix(bspump.unittest.TestCase):
    def test_matrix(self):
        matrix = bspump.matrix.TimeWindowMatrix(app=self.App, clock_driven=False)
        self.assertEqual(matrix.Array.shape, (1, 15))

    def test_matrix_add_column(self):
        matrix = bspump.matrix.TimeWindowMatrix(
            app=self.App, columns=3, clock_driven=False
        )
        start = matrix.TimeConfig.get_start()
        end = matrix.TimeConfig.get_end()
        row_index = matrix.add_row("abc")
        warming_up = matrix.WarmingUpCount.WUC[row_index]
        first_col = 4
        second_col = 5
        third_col = 6
        matrix.Array[row_index, 0] = first_col
        matrix.Array[row_index, 1] = second_col
        matrix.Array[row_index, 2] = third_col
        num_columns = matrix.Array.shape[1]
        matrix.add_column()

        self.assertEqual(matrix.TimeConfig.get_start(), start + matrix.Resolution)
        self.assertEqual(matrix.TimeConfig.get_end(), end + matrix.Resolution)
        self.assertEqual(matrix.WarmingUpCount.WUC[0], warming_up - 1)

        self.assertEqual(matrix.Array[row_index, 0], second_col)
        self.assertEqual(matrix.Array[row_index, 1], third_col)
        self.assertEqual(matrix.Array[row_index, 2], 0)
        self.assertEqual(matrix.Array.shape[1], num_columns)

    def test_matrix_add_row(self):
        matrix = bspump.matrix.TimeWindowMatrix(
            app=self.App, columns=3, clock_driven=False
        )
        row_index = matrix.add_row("abc")
        self.assertEqual(matrix.Array.shape[0], len(matrix.WarmingUpCount))

    # def test_matrix_close_row(self):
    # 	matrix = bspump.matrix.TimeWindowMatrix(app=self.App, columns=3, clock_driven=False)
    # 	row_index = matrix.add_row("abc")
    # 	self.assertFalse(row_index in matrix.ClosedRows.CR)
    # 	matrix.close_row(row_index)
    # 	self.assertTrue(row_index in matrix.ClosedRows.CR)
    # 	matrix.flush()
    # 	self.assertEqual(0, matrix.Array.shape[0])

    def test_matrix_get_column(self):
        columns = 10
        matrix = bspump.matrix.TimeWindowMatrix(
            app=self.App, resolution=1, columns=columns, clock_driven=False
        )
        cur_time = int(time.time())
        for i in range(columns):
            time_ = cur_time - i
            column_index = matrix.get_column(time_ + 0.5)
            self.assertEqual(column_index, columns - i - 1)

    def test_matrix_advance(self):
        columns = 10
        cur_time = int(time.time())
        matrix = bspump.matrix.TimeWindowMatrix(
            app=self.App,
            start_time=cur_time,
            resolution=1,
            columns=columns,
            clock_driven=False,
        )
        row_index = matrix.add_row("abc")

        target_ts = matrix.TimeConfig.get_start()
        added = matrix.advance(target_ts)
        self.assertGreater(added, 0)

        target_ts = matrix.TimeConfig.get_start() + matrix.Resolution
        added = matrix.advance(target_ts)
        self.assertGreater(added, 0)

        target_ts = matrix.TimeConfig.get_start() - matrix.Resolution
        added = matrix.advance(target_ts)
        self.assertEqual(added, 0)

        target_ts = matrix.TimeConfig.get_start() - 0.5 * matrix.Resolution
        added = matrix.advance(target_ts)
        self.assertEqual(added, 0)

        target_ts = matrix.TimeConfig.get_start() + 0.5 * matrix.Resolution
        added = matrix.advance(target_ts)
        self.assertGreater(added, 0)
