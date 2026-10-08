package ai.proception.glove.viewer;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.view.View;

/** The 100 taxels as a grid, one cell per value, dark to bright with pressure. */
final class TaxelGridView extends View {

    private static final int COLUMNS = 10;
    private static final int FULL_SCALE = 4095;

    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private int[] values = new int[0];

    TaxelGridView(Context context) {
        super(context);
    }

    void setValues(int[] taxels) {
        values = taxels;
        invalidate();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        if (values.length == 0) {
            return;
        }

        int rows = (values.length + COLUMNS - 1) / COLUMNS;
        float cell = Math.min(getWidth() / (float) COLUMNS, getHeight() / (float) rows);
        float pad = cell * 0.08f;

        for (int i = 0; i < values.length; i++) {
            int row = i / COLUMNS;
            int column = i % COLUMNS;
            float level = Math.min(1f, Math.max(0f, values[i] / (float) FULL_SCALE));
            fill.setColor(Color.rgb((int) (40 + 215 * level), (int) (40 + 60 * level), 60));
            canvas.drawRect(
                    column * cell + pad,
                    row * cell + pad,
                    (column + 1) * cell - pad,
                    (row + 1) * cell - pad,
                    fill);
        }
    }
}
